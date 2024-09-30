'''Upload all existing data from february to september'''
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import requests
from collections import defaultdict
import pytz
from datetime import datetime, timedelta, date
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi



# Get the authorization token
def get_token():
    url = "https://licacrm.co/api/auth/login"
    payload = {
        "login": "mail1809@softsvit.com",
        "password": "!POwj8yf+DKGK+7i8UhAIr+8UXH4="
    }

    response = requests.post(url, json=payload)

    # Check if the request was successful
    if response.status_code == 200:
        # Get the token from the response (assuming it's in JSON format)
        token =  response.json()['data']['token']
        bearer = {"authorization":f"Bearer {token}"}
        return bearer
        
    else:
        print("Failed to retrieve the token")


# List all managers ids and their names
def list_ids():
    bearer = get_token()
    managers_ids = {}

    '''We are retrieving ID's of managers leadered by 2 desk managers (3406 and 3407)'''
    managers = requests.get('https://licacrm.co/api/v2/calls/report/manager?manager_id=3406&date=2024-09-22|2024-09-27&', headers = bearer).json()['data']['managers']
    managers += requests.get('https://licacrm.co/api/v2/calls/report/manager?manager_id=3407&date=2024-09-22|2024-09-27&', headers = bearer).json()['data']['managers']

    for manager in managers:
        manager_name = manager["manager"].split(" (")[0]
        manager_id = manager["assign"].split("x")[1]

        mydict = {manager_name : manager_id}
        managers_ids.update(mydict)

    return managers_ids

# Request manager stats
def request_manager_stats(manager_id) -> list:
    try:
        bearer = get_token()
        headers = {"authorization": f"{bearer}"}
        response = requests.get(
            f'https://licacrm.co/api/v2/calls/report/hour?manager_id={manager_id}&date=2024-02-01|2024-09-30',
            headers=headers
        )
        response.raise_for_status()
        return response.json()["data"]["hours"]
    except requests.RequestException as e:
        print(f"Error fetching manager stats: {e}")
        return []



# Format and aggregate manager stats
def get_stats():
    total_stats = {}
    managers = list_ids()

    for manager,id in managers.items():
        #Skip if the id belongs to a desk manager
        if (int(id) == 3406 or int(id) == 3407):
            continue

        stats = request_manager_stats(id)
        kyiv_timezone = pytz.timezone('Europe/Kyiv')
        brazil_timezone = pytz.timezone('Etc/GMT+3')

        # Aggregate data by date
        aggregated_data = defaultdict(lambda: {'all_cnt': 0, 'unique_cnt': 0, 'duration': 0})
        
        for entry in stats:
            time_str = entry['time']
            time_gmt_plus_3 = kyiv_timezone.localize(datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S'))
            time_gmt_minus_3 = time_gmt_plus_3.astimezone(brazil_timezone)
            date_gmt_minus_3 = time_gmt_minus_3.date()  # Convert to date object

            aggregated_data[date_gmt_minus_3]['all_cnt'] += entry['all_cnt'] or 0
            aggregated_data[date_gmt_minus_3]['unique_cnt'] += entry['unique_cnt'] or 0
            aggregated_data[date_gmt_minus_3]['duration'] += entry['duration'] or 0


        # Initialize stats dictionary
        total_stats_manager = {}

        inserted_date_dt = datetime.strptime("9/29/24", "%m/%d/%y")
        inserted_date = inserted_date_dt.date()

        first_date_dt = datetime.strptime("2/1/24", "%m/%d/%y")
        first_date = first_date_dt.date()

        # Process each date
        for date_, totals in aggregated_data.items():

            if first_date <= date_ <= inserted_date:
                total_stats_manager[str(f"{manager}_{date_}")] = {
                    "name": manager,
                    "calls": totals['all_cnt'],
                    "uniques": totals['unique_cnt'],
                    "minutes": totals['duration'],
                    "date": str(date_),
                }
        total_stats.update(total_stats_manager)

    return total_stats



# Start MongoDB Server
CONNECTION_STRING = "mongodb+srv://nascimentojosue2002:976Q8rdG4GYQ64kc@cluster0.nbpxb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(CONNECTION_STRING)
db = client['Softsvit']
collection = db['manager-stats']

managers_stats = get_stats()
for name,stats in managers_stats.items():
    # Data to insert
    data = {
        "name": stats["name"],
        "calls": stats["calls"],
        "uniques": stats["uniques"],
        "minutes": stats["minutes"],
        "date": stats["date"]
}

    # Append data to collection
    insert_result = collection.insert_one(data)

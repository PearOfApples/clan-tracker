import requests
import copy
import math
from pprint import pprint
from ratelimit import limits, sleep_and_retry
from tabulate import tabulate

LOGIN_TEMPLE_ID = 2124
MAX_TOTAL_LEVEL = 2277
MAX_SINGLE_LEVEL = 99
ALL_PETS = 56
GAME_MODE = {
  0 : 'Main',
  1 : 'IM',
  2 : 'UIM',
  3 : 'HCIM'
}
CLOG_PAGES = {
    "Champion's cape": "Other/Champion's Challenge",
    "Fire cape": "Bosses/The Fight Caves",
    "Infernal cape": "Bosses/The Inferno",
    "CoX KC": "Raids/Chambers of Xeric/0",
    "CoX CM KC": "Raids/Chambers of Xeric/1",
    "ToB KC": "Raids/Theatre of Blood/0",
    "ToB HM KC": "Raids/Theatre of Blood/2",
    "ToA Expert KC": "Raids/Tombs of Amascut/2",
    "Cursed phalanx": "Raids/Tombs of Amascut"
  }
PARSED_CLOG = {
    "Champion's cape": 0,
    "Fire cape": 0,
    "Infernal cape": 0,
    "CoX KC": 0,
    "CoX CM KC": 0,
    "ToB KC": 0,
    "ToB HM KC": 0,
    "ToA Expert KC": 0,
    "Cursed phalanx": 0,
    "Pets": 0,
    "Total": 0
  }
POINT_CALCULATOR = {
    "Champion's cape": 2,
    "Fire cape": 1,
    "Infernal cape": 5,
  }

@sleep_and_retry
@limits(calls=5, period=300)
def get_temple_group_members(group_id):
  return requests.get('https://templeosrs.com/api/groupmembers.php?id={}'.format(group_id)).json()

@sleep_and_retry
@limits(calls=25, period=60)
def get_member_gamemode(member):
  return requests.get('https://templeosrs.com/api/player_info.php?player={}'.format(member)).json()

@sleep_and_retry
@limits(calls=25, period=60)
def get_member_stats(member):
  return requests.get('https://templeosrs.com/api/player_stats.php?player={}'.format(member), params={'bosses': 1}).json()

def get_collectionlog(member):
  return requests.get('https://api.collectionlog.net/collectionlog/user/{}'.format(member)).json()

def get_collectionlog_pets(member):
  return requests.get('https://api.collectionlog.net/items/user/{}'.format(member), params={'pageName': 'All Pets'}).json()

def parse_collectionlog(clog, clog_pets):
  parsed_clog = copy.deepcopy(PARSED_CLOG)
  for k,v in CLOG_PAGES.items():
    tab = v.split("/")[0]
    page = v.split("/")[1]

    if k.split(" ")[-1] == 'KC':
      parsed_clog[k] = clog['collectionLog']['tabs'][tab][page]['killCount'][int(v.split("/")[-1])]['amount']
      continue
    for item in clog['collectionLog']['tabs'][tab][page]['items']:
      if item['name'] == k and item['obtained']:
        parsed_clog[k] = item['quantity']
  parsed_clog['Pets'] = clog_pets['obtainedCount']
  parsed_clog['Total'] = clog['collectionLog']['uniqueObtained']

  return parsed_clog

def check_skill_cape_and_max(stats):
  skill_cape = False
  maxed = False
  if stats['Overall_level'] == 2277:
    maxed = True
  for k,v in stats.items():
    if '_level' in k and v == 99:
      skill_cape = True

  return skill_cape, maxed

def compute_points(player_tracker):
  points = 0
  for k,v  in POINT_CALCULATOR.items():
      if player_tracker['Collection Log'][k] > 0:
        points += v
  
  if player_tracker['Skill Cape']:
    points += 1
  if player_tracker['Maxed']:
    points += 3

  if player_tracker['Collection Log']['Pets'] == ALL_PETS:
    points += 5

  cox_kc = player_tracker['Collection Log']['CoX CM KC'] + player_tracker['Collection Log']['CoX CM KC']
  tob_kc = player_tracker['Collection Log']['ToB KC'] + player_tracker['Collection Log']['ToB HM KC']
  toa_kc = player_tracker['Collection Log']['ToA Expert KC']

  if cox_kc >= 10 and tob_kc >= 10 and toa_kc >= 10:
    points +=1
  if cox_kc >= 100 and tob_kc >= 100 and toa_kc >= 100:
    points += 2
  if cox_kc >= 100 and tob_kc >= 100 and player_tracker['Collection Log']['Cursed phalanx'] > 0:
    points += 4

  raids_kc = cox_kc + tob_kc + toa_kc
  points += math.floor(raids_kc / 250)
  points += math.floor(player_tracker['Total XP'] / 50000000)
  points += math.floor(player_tracker['Collection Log']['Total'] / 100)
  points += math.floor(player_tracker['Collection Log']['Pets'] / 5)

  return points

def track_players():
  player_tracker = {}

  for member in get_temple_group_members(LOGIN_TEMPLE_ID):
    gamemode = GAME_MODE[get_member_gamemode(member)['data']['Game mode']]
    player_tracker[member] = {'Type': gamemode, 'EHB': 0, 'EHP': 0, 'Collection Log': {}, 'Skill Cape' : False, 'Maxed': False, 'Total XP': 0, 'Points' : 0}
    
    stats = get_member_stats(member)['data']
    if gamemode == 'Main':
      player_tracker[member]['EHB'] = stats['Ehb']
      player_tracker[member]['EHP'] = stats['Ehp']
    elif gamemode == 'IM' or gamemode == 'HCIM':
      player_tracker[member]['EHB'] = stats['Im_ehb']
      player_tracker[member]['EHP'] = stats['Im_ehp']
    elif gamemode == 'UIM':
      player_tracker[member]['EHB'] = stats['Ehb']
      player_tracker[member]['EHP'] = stats['Uim_ehp']
    else:
      print('unknown gamemode!')
      exit(1)
    
    skill_cape_max_tracker = check_skill_cape_and_max(stats)
    player_tracker[member]['Skill Cape'] = skill_cape_max_tracker[0]
    player_tracker[member]['Maxed'] = skill_cape_max_tracker[1]
    player_tracker[member]['Total XP'] = stats['Overall']
    
    clog = get_collectionlog(member)
    clog_pets = get_collectionlog_pets(member)
    try:
      player_tracker[member]['Collection Log'] = parse_collectionlog(clog, clog_pets)
    except:
      player_tracker.pop(member)
      continue

    player_tracker[member]['Points'] = compute_points(player_tracker[member])

  member_list = []
  for member in player_tracker:
    member_list.append([member, player_tracker[member]['Points']])

  sorted_members = sorted(member_list, key=lambda x: x[1], reverse=True)
  print(tabulate(sorted_members, headers=["RSN", "Points"]))

  with open('output/detailed_tracking.txt', 'w') as f:
    pprint(player_tracker, f)
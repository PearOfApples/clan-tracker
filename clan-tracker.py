import redis
from src import playertracker

if __name__ == "__main__":
  pool = redis.ConnectionPool(host='localhost', port=6379, db=0)
  r = redis.Redis(connection_pool=pool)
  playertracker.track_players(r)
  playertracker.compute_ranks(r)
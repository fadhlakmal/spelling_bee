pake venv kalo mau

```console
python -m venv venv

# windows
venv\Scripts\activate

# linux
source venv/bin/activate
```

jalanin server bebas pake mana tapi kalo pake yg non-http ganti fungsi client dulu
```console
# non-http game server
python server.py

# http game server
python server_thread_http.py
```

jalanin 3 player (harus)
```console
# python wg_player.py {player_id}
python wg_player.py 1
python wg_player.py 2
python wg_player.py 3
```

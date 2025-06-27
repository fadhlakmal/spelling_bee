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

kalo pake lb run 3 server
```console
# python server_thread_http.py {port}
python server_thread_http.py 8889
python server_thread_http.py 8890
python server_thread_http.py 8891
```

run lb
```console
python lb_process.py
```

jalanin 3 player (harus)
```console
# python wg_player.py {player_id}
python wg_player.py 1
python wg_player.py 2
python wg_player.py 3
```

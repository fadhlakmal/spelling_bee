import os
import json
import base64
from glob import glob
import random
import shelve
import logging
import time
from typing import Dict, Any
import sqlite3

class PlayerServerInterface:
    def __init__(self):
        self.players = shelve.open('g.db',writeback=True)
        self.players['1']= "100,100"
        self.players['2']= "100,100"
        self.players['3']= "100,100"
        self.players_face=dict()
        self.players_face['1']=base64.b64encode(open('images/red.png',"rb").read())
        self.players_face['2']=base64.b64encode(open('images/pink.png',"rb").read())
        self.players_face['3']=base64.b64encode(open('images/cyan.png',"rb").read())

        self.player_ids = sorted(list(self.players_face.keys()))
        self.words_data = self._load_words_from_file('wordlist.txt')
        self.words = [item['word'] for item in self.words_data]
        self.time_limit = 30
        self.max_rounds = 10

        # SQLite connection
        self.conn = sqlite3.connect('game_state.db', check_same_thread=False)
        self._init_sqlite_state()

    def _init_sqlite_state(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS state
                     (key TEXT PRIMARY KEY, value TEXT)''')
        defaults = {
            'game_active': '0',
            'current_turn_index': '0',
            'current_round': '0',
            'lives': json.dumps({'1': 3, '2': 3, '3': 3}),
            'current_word': '',
            'current_word_data': '{}',
            'turn_start_time': '0'
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO state (key, value) VALUES (?, ?)", (k, v))
        self.conn.commit()

    def _set_state(self, key, value):
        c = self.conn.cursor()
        c.execute("REPLACE INTO state (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def _get_state(self, key, default=None):
        c = self.conn.cursor()
        c.execute("SELECT value FROM state WHERE key=?", (key,))
        row = c.fetchone()
        return row[0] if row else default

    def _load_words_from_file(self, filename):
        words = []
        try:
            with open(filename, 'r') as f:
                for line in f:
                    parts = line.strip().split(',', 2)
                    if len(parts) == 3:
                        words.append({'word': parts[0].strip(), 'type': parts[1].strip(), 'definition': parts[2].strip()})
        except FileNotFoundError:
            logging.error(f"Wordlist file {filename} not found.")
        return words

    def _setup_new_turn(self):
        if not self.words:
            logging.error("No words loaded for the game.")
            self._set_state('game_active', '0')
            return

        current_word_data = random.choice(self.words_data)
        self._set_state('current_word_data', json.dumps(current_word_data))
        self._set_state('current_word', current_word_data['word'])
        self._set_state('game_active', '1')
        self._set_state('turn_start_time', str(time.time()))
        logging.warning(f"New turn for player {self._get_current_player_id()}. Word is {current_word_data['word']}")

    def _get_current_player_id(self):
        idx = int(self._get_state('current_turn_index') or 0)
        return self.player_ids[idx]

    def get_all_players(self,params=[]):
        return dict(status='OK',players=list(self.players_face.keys()))

    def get_players_face(self, params=[]):
        pnum=params[0]
        try:
            return dict(status='OK',face=self.players_face[pnum].decode())
        except Exception as ee:
            return dict(status='ERROR')

    def set_location(self,params=[]):
        pnum = params[0]
        x = params[1]
        y = params[2]
        try:
            self.players[pnum]=f"{x},{y}"
            self.players.sync()
            return dict(status='OK', player=pnum)
        except Exception as e:
            return dict(status='ERROR')

    def get_location(self,params=[]):
        pnum = params[0]
        try:
            return dict(status='OK',location=self.players[pnum])
        except Exception as ee:
            return dict(status='ERROR')

    def start_game(self, params=[]):
        self._set_state('current_turn_index', '0')
        self._set_state('game_active', '1')
        self._set_state('current_round', '0')
        self._set_state('lives', json.dumps({'1': 3, '2': 3, '3': 3}))
        self._setup_new_turn()
        return self.get_game_state()

    def get_game_state(self, params=[]):
        if self._get_state('game_active') != '1':
            return dict(status='OK', game_active=False, message='No active game. Player 1 can start.')

        current_turn_index = int(self._get_state('current_turn_index') or 0)
        current_player_id = self.player_ids[current_turn_index]
        current_word = self._get_state('current_word') or ''
        current_word_data = json.loads(self._get_state('current_word_data') or '{}')
        current_round = int(self._get_state('current_round') or 0)
        lives = json.loads(self._get_state('lives') or '{}')
        turn_start_time = float(self._get_state('turn_start_time') or 0)
        time_remaining = max(0, self.time_limit - int(time.time() - turn_start_time))

        return dict(
            status='OK',
            game_active=True,
            current_player_id=current_player_id,
            word=current_word,
            word_type=current_word_data.get('type', ''),
            word_definition=current_word_data.get('definition', ''),
            current_round=current_round,
            max_rounds=self.max_rounds,
            lives=lives,
            time_remaining=time_remaining
        )

    def submit_spelling(self, params=[]):
        if self._get_state('game_active') != '1':
            return dict(status='ERROR', message='No active game.')

        try:
            player_id = params[0]
            spelling_attempt = params[1].lower()
        except IndexError:
            return dict(status='ERROR', message='Spelling submission requires player_id and a word.')

        current_turn_index = int(self._get_state('current_turn_index') or 0)
        current_player_id = self.player_ids[current_turn_index]
        if player_id != current_player_id:
            return dict(status='ERROR', message=f"Not your turn. It's player {current_player_id}'s turn.")

        turn_start_time = float(self._get_state('turn_start_time') or 0)
        time_elapsed = time.time() - turn_start_time
        current_word = self._get_state('current_word') or ''
        current_word_data = json.loads(self._get_state('current_word_data') or '{}')
        lives = json.loads(self._get_state('lives') or '{}')

        if time_elapsed > self.time_limit:
            is_correct = False
            message = f"Time's up! The correct spelling was: {current_word}"
        else:
            is_correct = (spelling_attempt == current_word)
            if is_correct:
                message = f"Correct!"
            else:
                message = f"Incorrect. The correct spelling was: {current_word}"

        points_earned = 0
        if not is_correct:
            lives[player_id] -= 1
            if lives[player_id] <= 0:
                lives[player_id] = 0
                message += f" Player {player_id} is eliminated!"
        self._set_state('lives', json.dumps(lives))

        # Find next player with lives > 0
        next_player_found = False
        for _ in range(len(self.player_ids)):
            current_turn_index = (current_turn_index + 1) % len(self.player_ids)
            if lives[self.player_ids[current_turn_index]] > 0:
                next_player_found = True
                break
        self._set_state('current_turn_index', str(current_turn_index))

        if not next_player_found:
            winner_message = "Game over! All players eliminated."
            self._set_state('game_active', '0')
            return dict(
                status='OK',
                game_active=False,
                message=winner_message,
                final_lives=lives
            )

        active_players = [pid for pid, lives_count in lives.items() if lives_count > 0]
        if len(active_players) <= 1:
            if len(active_players) == 1:
                winner_id = active_players[0]
                winner_message = f"Game over! Player {winner_id} wins!"
            else:
                winner_message = "Game over! It's a draw!"

            self._set_state('game_active', '0')
            return dict(
                status='OK',
                game_active=False,
                message=winner_message,
                last_turn=dict(
                    player_id=player_id,
                    word=current_word,
                    word_type=current_word_data.get('type', ''),
                    word_definition=current_word_data.get('definition', ''),
                    attempt=spelling_attempt,
                    correct=is_correct,
                    points_earned=points_earned
                ),
                final_lives=lives
            )

        self._set_state('current_turn_index', str(current_turn_index))
        self._setup_new_turn()

        state: Dict[str, Any] = self.get_game_state()
        state['message'] = message
        state['last_turn'] = dict(
            player_id=player_id,
            word=current_word,
            word_type=current_word_data.get('type', ''),
            word_definition=current_word_data.get('definition', ''),
            attempt=spelling_attempt,
            correct=is_correct,
            points_earned=points_earned
        )
        return state


if __name__=='__main__':
    p = PlayerServerInterface()
    p.set_location(['1',100,100])
    print(p.get_location('1'))
    p.set_location(['2',120,100])
    print(p.get_location('2'))
    print(p.get_players_face('1'))
    print(p.get_all_players())
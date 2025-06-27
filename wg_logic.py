import os
import json
import base64
from glob import glob
import random
import sqlite3
import logging
from contextlib import contextmanager

class PlayerServerInterface:
    def __init__(self):
        self.db_path = 'g.db.sqlite'
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        # Players table
        c.execute('''CREATE TABLE IF NOT EXISTS players (id TEXT PRIMARY KEY, location TEXT)''')
        for pid in ['1', '2', '3']:
            c.execute('INSERT OR IGNORE INTO players (id, location) VALUES (?, ?)', (pid, '100,100'))
        # Game state table
        c.execute('''CREATE TABLE IF NOT EXISTS game_state (
            key TEXT PRIMARY KEY, value TEXT
        )''')
        # Set default state if not present
        defaults = {
            'current_turn_index': '0',
            'current_word': '',
            'game_active': '0',
            'scores': json.dumps({'1': 0, '2': 0, '3': 0}),
            'current_round': '0',
            'max_rounds': '10',
            'words': json.dumps(["python", "algorithm", "network", "socket", "database", "programming", "interface", "threading", "dictionary", "encryption", "protocol", "variable", "function", "class", "inheritance", "exception"]),
            'player_ids': json.dumps(['1', '2', '3'])
        }
        for k, v in defaults.items():
            c.execute('INSERT OR IGNORE INTO game_state (key, value) VALUES (?, ?)', (k, v))
        conn.commit()
        conn.close()

    def _get_state(self, key, as_json=False):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT value FROM game_state WHERE key=?', (key,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(row[0]) if as_json else row[0]

    def _set_state(self, key, value, as_json=False):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        v = json.dumps(value) if as_json else str(value)
        c.execute('UPDATE game_state SET value=? WHERE key=?', (v, key))
        conn.commit()
        conn.close()

    def _get_scores(self):
        return self._get_state('scores', as_json=True)
    def _set_scores(self, scores):
        self._set_state('scores', scores, as_json=True)
    def _get_player_ids(self):
        return self._get_state('player_ids', as_json=True)
    def _get_words(self):
        return self._get_state('words', as_json=True)

    def _get_current_player_id(self):
        idx = int(self._get_state('current_turn_index'))
        return self._get_player_ids()[idx]

    def get_all_players(self, params=[]):
        return dict(status='OK', players=self._get_player_ids())

    def set_location(self, params=[]):
        pnum, x, y = params[0], params[1], params[2]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE players SET location=? WHERE id=?', (f"{x},{y}", pnum))
        conn.commit()
        conn.close()
        return dict(status='OK', player=pnum)

    def get_location(self, params=[]):
        pnum = params[0]
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT location FROM players WHERE id=?', (pnum,))
        row = c.fetchone()
        conn.close()
        return dict(status='OK', location=row[0] if row else None)

    def start_game(self, params=[]):
        self._set_state('current_turn_index', 0)
        self._set_state('game_active', 1)
        self._set_state('current_round', 0)
        self._set_scores({'1': 0, '2': 0, '3': 0})
        self._setup_new_turn()
        return self.get_game_state()

    def _setup_new_turn(self):
        import random
        word = random.choice(self._get_words())
        self._set_state('current_word', word)
        self._set_state('game_active', 1)

    def get_game_state(self, params=[]):
        if not int(self._get_state('game_active')):
            return dict(status='OK', game_active=False, message='No active game. Player 1 can start.')
        return dict(
            status='OK',
            game_active=True,
            current_player_id=self._get_current_player_id(),
            word=self._get_state('current_word'),
            current_round=int(self._get_state('current_round')),
            max_rounds=int(self._get_state('max_rounds')),
            scores=self._get_scores()
        )

    def submit_spelling(self, params=[]):
        if not int(self._get_state('game_active')):
            return dict(status='ERROR', message='No active game.')
        player_id = params[0]
        spelling_attempt = params[1].lower()
        current_word = self._get_state('current_word')
        is_correct = (spelling_attempt == current_word)
        scores = self._get_scores()
        if is_correct:
            scores[player_id] += len(current_word)
            message = f"Correct! You earned {len(current_word)} points."
        else:
            message = f"Incorrect. The correct spelling was: {current_word}"
        self._set_scores(scores)
        idx = int(self._get_state('current_turn_index'))
        player_ids = self._get_player_ids()
        idx = (idx + 1) % len(player_ids)
        self._set_state('current_turn_index', idx)
        current_round = int(self._get_state('current_round'))
        if idx == 0:
            current_round += 1
            self._set_state('current_round', current_round)
        max_rounds = int(self._get_state('max_rounds'))
        if current_round >= max_rounds:
            max_score = max(scores.values())
            winners = [pid for pid, score in scores.items() if score == max_score]
            if len(winners) > 1:
                winner_message = f"Game over! It's a tie between players {', '.join(winners)} with {max_score} points!"
            else:
                winner_message = f"Game over! Player {winners[0]} wins with {max_score} points!"
            self._set_state('game_active', 0)
            return dict(
                status='OK',
                game_active=False,
                message=winner_message,
                last_turn=dict(
                    player_id=player_id,
                    word=current_word,
                    attempt=spelling_attempt,
                    correct=is_correct,
                    points_earned=len(current_word) if is_correct else 0
                ),
                final_scores=scores
            )
        self._setup_new_turn()
        state = self.get_game_state()
        state['message'] = message
        state['last_turn'] = dict(
            player_id=player_id,
            word=current_word,
            attempt=spelling_attempt,
            correct=is_correct,
            points_earned=len(current_word) if is_correct else 0
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
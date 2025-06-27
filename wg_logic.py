import os
import json
import base64
from glob import glob
import random
import shelve
import logging
import time
from typing import Dict, Any

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
        self.current_turn_index = 0
        self.words_data = self._load_words_from_file('wordlist.txt')
        self.words = [item['word'] for item in self.words_data]
        self.current_word = ""
        self.current_word_data = {}
        self.game_active = False
        self.lives = {'1': 3, '2': 3, '3': 3}
        self.time_limit = 30
        self.turn_start_time = 0
        self.current_round = 0
        self.max_rounds = 10

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
            self.game_active = False
            return
        
        self.current_word_data = random.choice(self.words_data)
        self.current_word = self.current_word_data['word']
        self.game_active = True
        self.turn_start_time = time.time()
        logging.warning(f"New turn for player {self.player_ids[self.current_turn_index]}. Word is {self.current_word}")

    def _get_current_player_id(self):
        return self.player_ids[self.current_turn_index]

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
        self.current_turn_index = 0
        self.game_active = True
        self.current_round = 0
        self.lives = {'1': 3, '2': 3, '3': 3}
        self._setup_new_turn()
        return self.get_game_state()

    def get_game_state(self, params=[]):
        if not self.game_active:
            return dict(status='OK', game_active=False, message='No active game. Player 1 can start.')

        time_remaining = max(0, self.time_limit - int(time.time() - self.turn_start_time))

        return dict(
            status='OK',
            game_active=True,
            current_player_id=self._get_current_player_id(),
            word=self.current_word,
            word_type=self.current_word_data.get('type', ''),
            word_definition=self.current_word_data.get('definition', ''),
            current_round=self.current_round,
            max_rounds=self.max_rounds,
            lives=self.lives,
            time_remaining=time_remaining
        )

    def submit_spelling(self, params=[]):
        if not self.game_active:
            return dict(status='ERROR', message='No active game.')

        try:
            player_id = params[0]
            spelling_attempt = params[1].lower()
        except IndexError:
            return dict(status='ERROR', message='Spelling submission requires player_id and a word.')

        if player_id != self._get_current_player_id():
            return dict(status='ERROR', message=f"Not your turn. It's player {self._get_current_player_id()}'s turn.")

        time_elapsed = time.time() - self.turn_start_time
        if time_elapsed > self.time_limit:
            is_correct = False
            message = f"Time's up! The correct spelling was: {self.current_word}"
        else:
            is_correct = (spelling_attempt == self.current_word)
            if is_correct:
                message = f"Correct!"
            else:
                message = f"Incorrect. The correct spelling was: {self.current_word}"
        
        points_earned = 0
        if not is_correct:
            self.lives[player_id] -= 1
            if self.lives[player_id] <= 0:
                self.lives[player_id] = 0
                message += f" Player {player_id} is eliminated!"

        next_player_found = False
        for _ in range(len(self.player_ids)):
            self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)
            if self.lives[self.player_ids[self.current_turn_index]] > 0:
                next_player_found = True
                break
        
        if not next_player_found:
            winner_message = "Game over! All players eliminated."
            self.game_active = False
            return dict(
                status='OK',
                game_active=False,
                message=winner_message,
                final_lives=self.lives
            )

        active_players = [pid for pid, lives_count in self.lives.items() if lives_count > 0]
        if len(active_players) <= 1:
            if len(active_players) == 1:
                winner_id = active_players[0]
                winner_message = f"Game over! Player {winner_id} wins!"
            else:
                winner_message = "Game over! It's a draw!"
            
            self.game_active = False
            return dict(
                status='OK',
                game_active=False,
                message=winner_message,
                last_turn=dict(
                    player_id=player_id,
                    word=self.current_word,
                    word_type=self.current_word_data.get('type', ''),
                    word_definition=self.current_word_data.get('definition', ''),
                    attempt=spelling_attempt,
                    correct=is_correct,
                    points_earned=points_earned
                ),
                final_lives=self.lives
            )
        
        self._setup_new_turn()
        
        state: Dict[str, Any] = self.get_game_state()
        state['message'] = message
        state['last_turn'] = dict(
            player_id=player_id,
            word=self.current_word, 
            word_type=self.current_word_data.get('type', ''),
            word_definition=self.current_word_data.get('definition', ''),
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
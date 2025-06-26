import os
import json
import base64
from glob import glob
import random
import shelve
import logging

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
        self.words = ["python", "algorithm", "network", "socket", "database", "programming", 
                      "interface", "threading", "dictionary", "encryption", "protocol", 
                      "variable", "function", "class", "inheritance", "exception"]
        self.current_word = ""
        self.game_active = False
        self.scores = {'1': 0, '2': 0, '3': 0}
        self.current_round = 0
        self.max_rounds = 10

    def _setup_new_turn(self):
        self.current_word = random.choice(self.words)
        self.game_active = True
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
        self.scores = {'1': 0, '2': 0, '3': 0}
        self._setup_new_turn()
        return self.get_game_state()

    def get_game_state(self, params=[]):
        if not self.game_active:
            return dict(status='OK', game_active=False, message='No active game. Player 1 can start.')

        return dict(
            status='OK',
            game_active=True,
            current_player_id=self._get_current_player_id(),
            word=self.current_word,
            current_round=self.current_round,
            max_rounds=self.max_rounds,
            scores=self.scores
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

        is_correct = (spelling_attempt == self.current_word)
        
        if is_correct:
            self.scores[player_id] += len(self.current_word)
            message = f"Correct! You earned {len(self.current_word)} points."
        else:
            message = f"Incorrect. The correct spelling was: {self.current_word}"
        
        self.current_turn_index = (self.current_turn_index + 1) % len(self.player_ids)
        
        if self.current_turn_index == 0:
            self.current_round += 1
        
        if self.current_round >= self.max_rounds:
            winner_id = max(self.scores, key=self.scores.get)
            max_score = self.scores[winner_id]
            
            winners = [pid for pid, score in self.scores.items() if score == max_score]
            
            if len(winners) > 1:
                winner_message = f"Game over! It's a tie between players {', '.join(winners)} with {max_score} points!"
            else:
                winner_message = f"Game over! Player {winner_id} wins with {max_score} points!"
            
            self.game_active = False
            return dict(
                status='OK',
                game_active=False,
                message=winner_message,
                last_turn=dict(
                    player_id=player_id,
                    word=self.current_word,
                    attempt=spelling_attempt,
                    correct=is_correct,
                    points_earned=len(self.current_word) if is_correct else 0
                ),
                final_scores=self.scores
            )
        
        self._setup_new_turn()
        
        state = self.get_game_state()
        state['message'] = message
        state['last_turn'] = dict(
            player_id=player_id,
            word=self.current_word, 
            attempt=spelling_attempt,
            correct=is_correct,
            points_earned=len(self.current_word) if is_correct else 0
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
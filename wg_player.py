import pygame
import sys
import socket
import logging
import json
import pyttsx3
import threading

pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Spelling Bee Game")
clock = pygame.time.Clock()
FPS = 30

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GOLD = (255, 215, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
FONT = pygame.font.Font(None, 80)
SMALL_FONT = pygame.font.Font(None, 40)
MSG_FONT = pygame.font.Font(None, 32)
INPUT_FONT = pygame.font.Font(None, 50)

tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150)  
tts_engine.setProperty('volume', 0.9)

tts_lock = threading.Lock()
currently_speaking = False

def speak_word(word, repeat=1):
    global currently_speaking
    
    def speak_thread():
        global currently_speaking
        with tts_lock:
            currently_speaking = True
            for _ in range(repeat):
                tts_engine.say(word)
                tts_engine.runAndWait()
                pygame.time.wait(500)
            currently_speaking = False
    
    threading.Thread(target=speak_thread, daemon=True).start()

class ClientInterface:
    def __init__(self):
        self.server_address = ('localhost', 8889)

    def send_request(self, request_line):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(self.server_address)
            http_request = f"{request_line}\r\nHost: {self.server_address[0]}\r\nConnection: close\r\n\r\n"
            sock.sendall(http_request.encode())
            
            response = b""
            while True:
                data = sock.recv(1024)
                if not data:
                    break
                response += data
            
            headers_raw, body_raw = response.split(b'\r\n\r\n', 1)
            headers = headers_raw.decode().split('\r\n')
            status_line = headers[0]
            
            if status_line.startswith("HTTP/1.0 200 OK"):
                return json.loads(body_raw)
            else:
                logging.warning(f"Server returned error: {status_line}")
                return {'status': 'ERROR', 'message': f'Server error: {status_line}'}

        except Exception as e:
            logging.warning(f"Error during HTTP request: {e}")
            return {'status': 'ERROR', 'message': 'Connection error'}
        finally:
            sock.close()

    def start_game(self):
        return self.send_request("GET /game/start HTTP/1.0")

    def get_game_state(self):
        return self.send_request("GET /game/state HTTP/1.0")

    def submit_spelling(self, player_id, spelling):
        return self.send_request(f"GET /game/submit?player_id={player_id}&spelling={spelling} HTTP/1.0")


def draw_text(text, font, color, surface, x, y, center=True):
    textobj = font.render(text, True, color)
    textrect = textobj.get_rect()
    if center:
        textrect.center = (x, y)
    else:
        textrect.topleft = (x, y)
    surface.blit(textobj, textrect)

def draw_input_box(input_text, active):
    input_box = pygame.Rect(WIDTH // 4, HEIGHT // 2 + 30, WIDTH // 2, 60)
    color = GOLD if active else BLACK
    pygame.draw.rect(screen, color, input_box, 2)
    
    text_surface = INPUT_FONT.render(input_text, True, BLACK)
    
    text_rect = text_surface.get_rect(center=input_box.center)
    screen.blit(text_surface, text_rect)

def game_loop(player_id):
    client = ClientInterface()
    message = "Connecting to game..."
    input_text = ""
    input_active = True
    last_result = None
    current_word = ""
    word_spoken = False
    
    replay_button = pygame.Rect(WIDTH // 2 - 60, HEIGHT // 2 + 180, 120, 40)
    
    while True:
        screen.fill(WHITE)
        game_state = client.get_game_state()

        if game_state.get('status') != 'OK':
            draw_text("Error connecting to server", SMALL_FONT, RED, screen, WIDTH // 2, HEIGHT // 2)
            
        elif not game_state.get('game_active'):
            msg = game_state.get('message', 'Waiting for game to start...')
            draw_text(msg, SMALL_FONT, BLACK, screen, WIDTH // 2, HEIGHT // 2)
            word_spoken = False  

            if 'final_scores' in game_state:
                y_pos = HEIGHT // 2 + 50
                draw_text("Final Scores:", SMALL_FONT, BLACK, screen, WIDTH // 2, y_pos)
                
                for pid, score in game_state['final_scores'].items():
                    y_pos += 40
                    draw_text(f"Player {pid}: {score}", SMALL_FONT, BLACK, screen, WIDTH // 2, y_pos)
            
            if player_id == '1':
                draw_text("Press S to start a new game", SMALL_FONT, BLACK, screen, WIDTH // 2, HEIGHT - 100)
                
        else:
            current_player_id = game_state.get('current_player_id')
            is_my_turn = (player_id == current_player_id)

            current_round = game_state.get('current_round', 0)
            max_rounds = game_state.get('max_rounds', 10)
            draw_text(f"Round {current_round + 1} of {max_rounds}", SMALL_FONT, BLACK, screen, WIDTH // 2, 30)
            
            scores = game_state.get('scores', {})
            score_text = " | ".join([f"Player {pid}: {score}" for pid, score in scores.items()])
            draw_text(score_text, SMALL_FONT, BLACK, screen, WIDTH // 2, 70)
            
            if is_my_turn:
                new_word = game_state.get('word', '')
                
                if new_word != current_word:
                    current_word = new_word
                    word_spoken = False
                
                if not word_spoken and current_word:
                    speak_word(current_word)
                    word_spoken = True
                
                draw_text("Spell this word:", SMALL_FONT, BLACK, screen, WIDTH // 2, HEIGHT // 2 - 100)
                
                if word_spoken:
                    draw_text("Listen and spell", FONT, BLUE, screen, WIDTH // 2, HEIGHT // 2 - 40)
                
                pygame.draw.rect(screen, BLUE, replay_button)
                draw_text("Replay Word", MSG_FONT, WHITE, screen, replay_button.centerx, replay_button.centery)
                
                draw_input_box(input_text, input_active)
                draw_text("Type the word and press Enter", SMALL_FONT, BLACK, screen, WIDTH // 2, HEIGHT // 2 + 120)
            else:
                draw_text(f"Waiting for Player {current_player_id}'s turn...", SMALL_FONT, BLACK, screen, WIDTH // 2, HEIGHT // 2)
                current_word = "" 
                word_spoken = False
            
            if 'last_turn' in game_state and game_state['last_turn']:
                last_turn = game_state['last_turn']
                result_color = GREEN if last_turn.get('correct', False) else RED
                
                y_pos = HEIGHT - 150
                draw_text(f"Last turn: Player {last_turn.get('player_id')} tried to spell:", SMALL_FONT, BLACK, screen, WIDTH // 2, y_pos)
                y_pos += 30
                draw_text(f"{last_turn.get('attempt')}", SMALL_FONT, result_color, screen, WIDTH // 2, y_pos)
                y_pos += 30
                
                if last_turn.get('correct', False):
                    draw_text(f"Correct! +{last_turn.get('points_earned', 0)} points", SMALL_FONT, GREEN, screen, WIDTH // 2, y_pos)
                else:
                    draw_text(f"Incorrect. Correct spelling: {last_turn.get('word', '')}", SMALL_FONT, RED, screen, WIDTH // 2, y_pos)
            
            if 'message' in game_state:
                draw_text(game_state['message'], MSG_FONT, BLACK, screen, WIDTH // 2, HEIGHT - 50)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if game_state.get('game_active', False) and player_id == game_state.get('current_player_id', ''):
                    if replay_button.collidepoint(event.pos) and current_word and not currently_speaking:
                        speak_word(current_word)
                
            elif event.type == pygame.KEYDOWN:
                if not game_state.get('game_active') and player_id == '1' and event.key == pygame.K_s:
                    client.start_game()
                    message = "New game started!"
                    continue
                
                current_player_id = game_state.get('current_player_id')
                if player_id == current_player_id and game_state.get('game_active'):
                    if event.key == pygame.K_RETURN:
                        if input_text:
                            response = client.submit_spelling(player_id, input_text)
                            message = response.get('message', 'Error processing submission.')
                            input_text = ""
                    elif event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                    else:
                        if event.unicode.isalpha() or event.unicode.isspace():
                            input_text += event.unicode

        pygame.display.flip()
        clock.tick(15)  

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("Usage: python wg_player.py <player_id>")
        print("Available IDs are 1, 2, 3.")
        sys.exit(1)
    
    player_id_arg = sys.argv[1]
    game_loop(player_id_arg)
import select
import socket

import sys

import pygame

from GameControllerServerMessages import *


class GameControllerServer(object):
    def __init__(self, game, port=7777, host='', min_players=1, max_players=2):
        '''
        Constructor

        Creates the actual server and sets up member variables

        @param game:  The pygame object necessary for passing on events
        @param port (default 7777):     Server port
        @param host (default localhost: Server host
        @param min_players (default 1): Minimum of players necessary to play
        @param max_players (default 1): Maximum of players to play in parallel
        '''
        self.game = game

        # Number of clients and map with id's
        self.clients = 0
        self.clientmap = {}

        # minimal and maximum numbers of players necessary for the game
        self.min_players = min_players
        self.max_players = max_players

        # outgoing client connections
        self.outputs = []

        # actual select server
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host,port))
        self.server.listen(max_players)


    def getid(self, client):
        '''
        Returns the ID of a player given his socket

        necessary for identifying players in pygame
        '''
        info = self.clientmap[client]
        return "@"+str(info[1])

    
    def sendMessage(self, message):
        '''
        Sends the given message to all connected devices

        @param message: message to be sent
        '''
        for o in self.outputs:
            try:
                o.send(message)
            except socket.SocketError:
                continue

        
    def startGame(self):
        '''
        Sends StartGame message to all connected devices
        and starts pygame
        '''
        self.sendMessage(START_GAME_MSG)
        self.game.start()


    def pauseGame(self):
        '''
        Sends PauseGame message to all connected devices
        and stops pygame
        '''
        self.sendMessage(PAUSE_GAME_MSG)
        self.game.pause()


    def resumeGame(self):
        '''
        Sends ResumeGame message to all connected devices
        and resumes pygame
        '''
        self.sendMessage(RESUME_GAME_MSG)
        self.game.resume()


    def stop(self):
        '''
        Stops the server and sends goodbye message to all clients
        '''
        self.sendMessage(GAME_STOPPED_MSG)
        self.running = False
        for o in self.outputs:
            try:
                o.close()
            except socket.SocketError, IOError:
                continue 
        self.server.close()
        sys.exit(0)


    def removePlayer(self, client):
        '''
        Removes a given clients from the input and output streams
        and pauses game if too few players remain

        @param client: socket to be removed
        '''
        self.clients -= 1
        self.inputs.remove(client)
        self.outputs.remove(client)
        self.game.removePlayer(self.getid(client))
        if self.clients < self.min_players:
            self.pauseGame()


    def serve(self):
        self.inputs = [self.server, sys.stdin]
        self.outputs = []

        self.running = 1
        self.started = False

        while self.running:
            try:
                inputready,outputready,exceptready = select.select(self.inputs, self.outputs, [])
            except select.error, e:
                break
            except socket.error, e:
                break
            except SystemExit:
                break
            except KeyboardInterrupt:
                break

            for s in inputready:
                if s == self.server:
                    client, address = self.server.accept()  

                    # Maximum not reached yet
                    if self.clients < self.max_players:
                        self.clients += 1
                        self.inputs.append(client)

                        self.clientmap[client] = address
                        self.outputs.append(client)
                        self.game.addPlayer(self.getid(client))

                        # Enough players to play
                        if self.clients == self.min_players:
                            # Game not started yet -> start it
                            if not self.started:
                                self.started = True
                                self.startGame()
                            # Game started before -> resume
                            else:
                                self.resumeGame()

                        # Not enough players yet
                        elif self.clients < self.min_players:
                            client.send(WAIT_FOR_PLAYER_MSG)

                        # Only send to current since others play already
                        else:
                            client.send(START_GAME_MSG)

                    # To many players
                    else:
                        client.send(TOO_MANY_PLAYERS_MSG)

                # Stdin only used for closing
                elif s == sys.stdin:
                    self.running = False

                # actual data
                else:
                    try:
                        data = s.recv(1024)

                        # Command received
                        if data:
                            pygame.event.post(pygame.event.Event(pygame.USEREVENT, {"key":data,"id":self.getid(s)}))

                        # Client left
                        else:
                            s.close()
                            self.removePlayer(s)

    
                    except socket.error, e:
                        self.removePlayer(s)

        self.stop()

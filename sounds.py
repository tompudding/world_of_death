import sys, pygame, glob, os

from pygame.locals import *
import pygame.mixer
import utils

pygame.mixer.init()

class Sounds(object):
    def __init__(self):
        self.talking = []
        self.player_damage = []
        self.wee_sounds = []

        for filename in glob.glob(utils.fix_path(os.path.join('resource','sounds','*.ogg'))):
            sound = pygame.mixer.Sound(filename)
            sound.set_volume(0.6)
            name = os.path.basename(filename)
            name = os.path.splitext(name)[0]
            if name.startswith('wee_'):
                self.wee_sounds.append(sound)
            setattr(self,name,sound)

    def stop_talking(self):
        for sound in self.talking:
            sound.stop()

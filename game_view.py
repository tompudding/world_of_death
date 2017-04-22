from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import actors

class ViewPos(object):
    def __init__(self, pos):
        self.pos = pos

class TimeOfDay(object):
    def __init__(self,t):
        self.Set(t)

    def Set(self,t):
        self.t = t

    def Daylight(self):
        #Direction will be
        a_k = 0.2
        d_k = 0.4
        r = 1000
        b = -1.5
        t = (self.t+0.75)%1.0
        a = t*math.pi*2
        z = math.sin(a)*r
        p = math.cos(a)*r
        x = math.cos(b)*p
        y = math.sin(b)*p
        if t < 0.125:
            #dawn
            colour  = [d_k*math.sin(40*t/math.pi) for i in (0,1,2)]
            colour[2] *= 1.4
            ambient = [a_k*math.sin(40*t/math.pi) for i in (0,1,2)]
        elif t < 0.375:
            #daylight
            colour = (d_k,d_k,d_k)
            ambient = (a_k,a_k,a_k)
        elif t < 0.5:
            #dusk
            colour = (d_k*math.sin(40*(t+0.25)/math.pi) for i in (0,1,2))
            ambient = [a_k*math.sin(40*(t+0.25)/math.pi) for i in (0,1,2)]
        else:
            x,y,z = (1,1,1)
            colour = (0,0,0)
            ambient = (0,0,0)

        return (-x,-y,-z),colour,ambient,ambient[0]/a_k

    def Ambient(self):
        t = (self.t+0.75)%1.0
        return (0.5,0.5,0.5)

    def Nightlight(self):
        #Direction will be

        return (1,3,-5),(0.25,0.25,0.4)


class GameView(ui.RootElement):
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.enemies = []
        #globals.ui_atlas = drawing.texture.TextureAtlas('ui_atlas_0.png','ui_atlas.txt',extra_names=False)
        self.viewpos = ViewPos(Point(0,0))

        self.game_over = False
        self.mouse_world = Point(0,0)
        self.mouse_pos = Point(0,0)
        #pygame.mixer.music.load('music.ogg')
        self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #skip titles for development of the main game

        self.light      = drawing.Quad(globals.light_quads)
        self.light.SetVertices(Point(0,0),
                               globals.screen_abs - Point(0,0),
                               0)

        self.timeofday = TimeOfDay(0.30)
        self.mode = modes.GameMode(self)
        self.StartMusic()
        #self.fixed_light = actors.FixedLight( Point(11,38),Point(26,9) )
        self.text_colour = (0,1,0,1)

        #self.map = GameMap('level1.txt',self)
        self.mode = modes.GameMode(self)
        #self.map.world_size = self.map.size * globals.tile_dimensions

    def StartMusic(self):
        return
        #globals.sounds.stop_talking()
        #globals.sounds.talking_intro.play()
        pygame.mixer.music.play(-1)
        pygame.mixer.music.set_volume(globals.music_volume)
        self.music_playing = True

    def Draw(self):
        drawing.ResetState()
        drawing.Translate(-self.viewpos.pos.x,-self.viewpos.pos.y,0)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture)
        #drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return

        self.t = t

        self.mouse_world = self.viewpos.pos + self.mouse_pos

    def GameOver(self):
        self.game_over = True
        self.mode = modes.GameOver(self)

    def KeyDown(self,key):
        self.mode.KeyDown(key)

    def KeyUp(self,key):
        if key == pygame.K_DELETE:
            if self.music_playing:
                self.music_playing = False
                pygame.mixer.music.set_volume(0)
            else:
                self.music_playing = True
                pygame.mixer.music.set_volume(globals.music_volume)
        self.mode.KeyUp(key)

    def MouseMotion(self,pos,rel,handled):
        world_pos = self.viewpos.pos + pos
        self.mouse_pos = pos

        self.mode.MouseMotion(world_pos,rel)

        return super(GameView,self).MouseMotion(pos,rel,handled)

    def MouseButtonDown(self,pos,button):
        if self.mode:
            pos = self.viewpos.pos + pos
            return self.mode.MouseButtonDown(pos,button)
        else:
            return False,False

    def MouseButtonUp(self,pos,button):
        if self.mode:
            pos = self.viewpos.pos + pos
            return self.mode.MouseButtonUp(pos,button)
        else:
            return False,False

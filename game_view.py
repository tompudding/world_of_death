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

class Background(object):
    width = 32768
    height = 704

    def __init__(self, filename):
        self.tc = globals.atlas.TextureSpriteCoords('%s.png' % filename)
        #Make a grid of quads
        self.quads = []
        tile_size = (32,32)
        for i in xrange(self.width/tile_size[0]):
            for j in xrange(self.height/tile_size[1]):
                quad = drawing.Quad(globals.quad_buffer, tc = self.tc)
                self.quads.append(quad)
                bl = Point(i*tile_size[0],j*tile_size[1])
                tr = Point((i+1)*tile_size[0], (j+1)*tile_size[1])
                quad.SetVertices(bl,tr,0)

class Spring(object):
    k = 0.03
    damping = 0.0025
    def __init__(self, x, y):
        self.target_height = y

        self.bottom = Point(x, 0)
        self.top = Point(x, y)

        self.velocity = 0

    def Update(self, elapsed):

        diff = self.top.y - self.target_height
        acc = -self.k * diff

        self.velocity += (acc * elapsed)
        self.velocity -= self.velocity * self.damping * elapsed
        self.top.y += (self.velocity * elapsed)


class Trapezoid(object):
    dark = (0, 0.2, 0.4, 0.9)
    light = (0.2, 0.5, 1, 0.8)
    colours = [ (dark, light, dark), (light, light, dark) ]
    def __init__(self, buf, left_spring, right_spring):
        self.triangles = [drawing.Triangle(buf) for i in xrange(2)]
        self.left_spring = left_spring
        self.right_spring = right_spring
        for i,t in enumerate(self.triangles):
            t.SetColours( self.colours[i] )
        self.set_vertices()

    def set_vertices(self):
        self.triangles[0].SetVertices( self.left_spring.bottom,
                                       self.left_spring.top,
                                       self.right_spring.bottom, 10 )
        self.triangles[1].SetVertices( self.left_spring.top,
                                       self.right_spring.top,
                                       self.right_spring.bottom, 10 )

class Water(object):
    spread = 0.05
    spacing = 15
    def __init__(self, parent, height):
        self.parent = parent
        self.left = 0
        self.height = height
        num_springs = globals.screen_showing.x*3 / self.spacing
        #num_springs = 2
        self.springs = [Spring(i*self.spacing, self.height) for i in xrange(num_springs)]

        self.buffer = drawing.TriangleBuffer(3*(num_springs-1)*2)
        self.last_update = None

        #try a test triangle
        self.trapezoids = []
        for i in xrange(num_springs-1):
            trapezoid = Trapezoid(self.buffer, self.springs[i], self.springs[i+1])
            self.trapezoids.append(trapezoid)



    def get_height(self, x):
        offset = x - self.left
        i = int(offset / self.spacing)
        j = i + 1
        partial = float(offset % self.spacing) / self.spacing

        left_height = self.springs[i].top.y
        right_height = self.springs[j].top.y

        return left_height + (right_height - left_height) * partial

    def jiggle(self, x, amount):
        n = int((x - self.left)/self.spacing)
        print 'jiggle at',x,n,len(self.trapezoids)
        self.springs[n].velocity += amount


    def Update(self):
        if self.last_update is None:
            self.last_update = globals.time
            return

        if self.parent.viewpos.pos.x - self.left > globals.screen_showing.x*1.1:
            #There's more than a whole screen of springs off to the left
            num_to_move = int((self.parent.viewpos.pos.x - self.left - globals.screen_showing.x) / self.spacing)
            self.springs = self.springs[num_to_move:]
            start = self.springs[-1].bottom.x + self.spacing
            for i in xrange(num_to_move):
                self.springs.append(Spring(start + i*self.spacing, self.height))
            self.left = self.springs[0].bottom.x

            for i in xrange(len(self.trapezoids)):
                self.trapezoids[i].left_spring = self.springs[i]
                self.trapezoids[i].right_spring = self.springs[i+1]


        elapsed = (globals.time - self.last_update) * globals.time_step
        self.last_update = globals.time

        l_deltas = [0 for i in xrange(len(self.springs))]
        r_deltas = [0 for i in xrange(len(self.springs))]

        for spring in self.springs:
            spring.Update(elapsed)

        #print elapsed,self.springs[45].top.y, self.springs[45].velocity

        #pull on each other
        for i in xrange(8):
            for j in xrange(len(self.springs)):
                if j > 0:
                    l_deltas[j] = self.spread * (self.springs[j].top.y - self.springs[j-1].top.y)
                    self.springs[j - 1].velocity += (l_deltas[j]*elapsed)
                if j < len(self.springs) - 1:
                    r_deltas[j] = self.spread * (self.springs[j].top.y - self.springs[j+1].top.y)
                    self.springs[j + 1].velocity += (r_deltas[j]*elapsed)

            for j in xrange(len(self.springs)):
                if j > 0:
                    self.springs[j - 1].top.y += l_deltas[j] * elapsed
                if j < len(self.springs) - 1:
                    self.springs[j + 1].top.y += r_deltas[j] * elapsed

        for trap in self.trapezoids:
            trap.set_vertices()

    def Draw(self):
        #drawing.ResetState()
        drawing.DrawNoTexture(self.buffer)

class GameView(ui.RootElement):
    water_height = 40
    light_spacing = 250
    light_height = 200
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        self.enemies = []
        #globals.ui_atlas = drawing.texture.TextureAtlas('ui_atlas_0.png','ui_atlas.txt',extra_names=False)
        self.viewpos = ViewPos(Point(0,0))
        #Make a big background. Making it large lets opengl take care of the texture coordinates
        #TODO: tie this in with the size of the map
        self.background = Background('tile')
        self.water = Water(parent = self, height = self.water_height)

        self.game_over = False
        self.mouse_world = Point(0,0)
        self.mouse_pos = Point(0,0)
        #pygame.mixer.music.load('music.ogg')
        self.music_playing = False
        super(GameView,self).__init__(Point(0,0),globals.screen)
        #skip titles for development of the main game

        #For the ambient light
        self.light      = drawing.Quad(globals.light_quads)
        self.light.SetVertices(Point(0,0),
                               globals.screen_showing - Point(0,0),
                               0)

        self.room_lights = []
        for i in xrange(5):
            self.lights_start = 0
            light = actors.Light(Point(i*self.light_spacing,self.light_height))
            self.room_lights.append(light)

        self.timeofday = TimeOfDay(0.3)
        self.mode = modes.GameMode(self)
        self.StartMusic()
        #self.fixed_light = actors.FixedLight( Point(11,38),Point(26,9) )
        self.text_colour = (0,1,0,1)

        #self.map = GameMap('level1.txt',self)
        self.mode = modes.GameMode(self)
        #self.map.world_size = self.map.size * globals.tile_dimensions
        self.boat = actors.Boat(Point(globals.screen_showing.x /2 ,self.water_height), self.water)
        self.boat.move_direction = Point(0.2,0)

        self.test_critter = actors.Critter(Point(600,200))

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
        drawing.Scale(globals.scale.x, globals.scale.y, 1)
        drawing.DrawAll(globals.quad_buffer,self.atlas.texture)
        #glEnable(GL_BLEND);
        #glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
        self.water.Draw()

        #drawing.DrawAll(globals.nonstatic_text_buffer,globals.text_manager.atlas.texture)

    def Update(self,t):
        if self.mode:
            self.mode.Update(t)

        if self.game_over:
            return

        self.t = t
        self.water.Update()
        self.boat.Update(t)
        self.test_critter.Update(t)

        self.viewpos.pos.x = self.boat.pos.x - globals.screen_showing.x/2

        if int((self.viewpos.pos.x - self.lights_start)/self.light_spacing) >= 1:
            #move the first to the last
            self.lights_start += self.light_spacing
            self.room_lights = self.room_lights[1:] + self.room_lights[:1]

            self.room_lights[-1].set_pos( Point(self.lights_start + (len(self.room_lights)-1)*self.light_spacing,self.light_height) )

        globals.mouse_world = self.viewpos.pos + self.mouse_pos

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
        #print globals.mouse_world

        self.mode.MouseMotion(world_pos,rel)

        return super(GameView,self).MouseMotion(pos,rel,handled)

    def MouseButtonDown(self,pos,button):
        self.water.jiggle(globals.mouse_world.x, -10)

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

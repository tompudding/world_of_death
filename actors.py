from globals.types import Point
from OpenGL.GL import *
import globals
import ui
import drawing
import os
import game_view
import random
import pygame
import cmath
import math
import numpy
import modes


class Actor(object):
    texture = None
    width   = None
    height  = None
    initial_health = 100
    max_square_speed = 10
    def __init__(self,pos):
        self.tc             = globals.atlas.TextureSpriteCoords('%s.png' % self.texture)
        self.quad           = drawing.Quad(globals.quad_buffer,tc = self.tc)
        self.size           = Point(self.width,self.height)
        self.corners = self.size, Point(-self.size.x,self.size.y), Point(-self.size.x,-self.size.y), Point(self.size.x,-self.size.y)
        #that's a weird order
        self.corners = [self.corners[2],self.corners[1],self.corners[0],self.corners[3]]
        self.corners        = [p*0.5 for p in self.corners]
        #self.corners_polar  = [(p.length(),((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        self.polar_offsets = [cmath.polar(p.x+p.y*1j)[1] for p in self.corners]
        print self.polar_offsets
        self.radius_square  = (self.size.x/2)**2 + (self.size.y/2)**2
        self.radius         = math.sqrt(self.radius_square)
        self.corners_euclid = [p for p in self.corners]
        self.last_update    = None
        self.dead           = False
        self.move_speed     = Point(0,0)
        self.angle_speed    = 0
        self.move_direction = Point(0,0)
        self.pos = None
        self.last_damage = 0
        self.health = self.initial_health
        self.interacting = None
        self.SetPos(pos)

        self.set_angle(0)

        self.hand_offset = Point(0,self.size.y*1.1)
        self.track_quads = []
        self.last_track = 0

    def mid_point(self):
        return self.pos + (self.size/2).Rotate(self.angle)

    def AdjustHealth(self,amount):
        self.health += amount
        if self.health > self.initial_health:
            self.health = self.initial_health
        if self.health < 0:
            #if self.dead_sound:
            #    self.dead_sound.play()
            self.health = 0
            self.dead = True
            self.Death()

    def damage(self, amount):
        if globals.time < self.last_damage + self.immune_duration:
            #woop we get to skip
            return
        self.last_damage = globals.time
        self.AdjustHealth(-amount)

    def SetPos(self,pos):
        self.pos = pos

        self.vertices = [((pos + corner)) for corner in self.corners_euclid]

        #bl = pos
        #tr = bl + self.size
        #bl = bl.to_int()
        #tr = tr.to_int()
        #self.quad.SetVertices(bl,tr,4)

        self.quad.SetAllVertices(self.vertices, 4)

    def TriggerCollide(self,other):
        pass

    def set_angle(self, angle):
        self.angle = angle%(2*math.pi)
        self.corners_polar  = [(p.length(),self.angle + self.polar_offsets[i]) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]

    def Update(self,t):
        self.Move(t)

    def hand_pos(self):
        return self.pos + self.hand_offset.Rotate(self.angle)

    def Move(self,t):

        if self.last_update == None:
            self.last_update = globals.time
            return
        elapsed = (globals.time - self.last_update)*globals.time_step
        self.last_update = globals.time

        angle_change = self.angle_speed*elapsed
        #self.set_angle(self.angle + angle_change)

        self.move_speed += self.move_direction.Rotate(self.angle)*elapsed
        if self.move_speed.SquareLength() > self.max_square_speed:
            self.move_speed = self.move_speed.unit_vector() * self.max_speed

        if self.interacting:
            self.move_speed = Point(0,0)

        amount = self.move_speed * elapsed

        self.SetPos(self.pos + amount)
        #self.SetPos(self.pos)

    def GetPos(self):
        return self.pos

    def GetPosCentre(self):
        return self.pos

    def click(self, pos, button):
        pass

    def unclick(self, pos, button):
        pass

    @property
    def screen_pos(self):
        p = (self.pos - globals.game_view.viewpos._pos)*globals.scale
        return p


class Light(object):
    z = 60
    def __init__(self,pos,radius = 400, intensity = 1):
        self.radius = radius
        self.width = self.height = radius
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.intensity = float(intensity)
        self.set_pos(pos)
        self.on = True
        self.append_to_list()

    def append_to_list(self):
        globals.lights.append(self)

    def set_pos(self,pos):
        self.world_pos = pos
        pos = pos
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)

    def Update(self,t):
        pass

    @property
    def screen_pos(self):
        p = self.pos
        return ((p[0] - globals.game_view.viewpos.pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos.pos.y)*globals.scale.y,self.z)

class NonShadowLight(Light):
    def append_to_list(self):
        globals.non_shadow_lights.append(self)

class ActorLight(object):
    z = 20
    def __init__(self,parent):
        self.parent = parent
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (1,1,1)
        self.radius = 100
        self.intensity = 1
        self.on = True
        globals.non_shadow_lights.append(self)

    def Update(self,t):
        self.vertices = [((self.parent.pos + corner*2)).to_int() for corner in self.parent.corners_euclid]
        self.quad.SetAllVertices(self.vertices, 0)

    @property
    def pos(self):
        return (self.parent.pos.x,self.parent.pos.y,self.z)

class FixedLight(object):
    z = 6
    def __init__(self,pos,size):
        #self.world_pos = pos
        self.pos = pos
        self.size = size
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.colour = (0.2,0.2,0.2)
        self.on = True
        globals.uniform_lights.append(self)
        self.pos = (self.pos.x,self.pos.y,self.z)
        box = (self.size)
        bl = Point(*self.pos[:2])
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)


class ConeLight(object):
    width = 700
    height = 700
    z = 60
    def __init__(self,pos,angle,width):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.colour = (1,1,1)
        self.initial_angle = angle
        self.angle = angle
        self.angle_width = width
        self.on = True
        pos = pos
        self.world_pos = pos
        self.pos = (pos.x,pos.y,self.z)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        globals.cone_lights.append(self)

    @property
    def screen_pos(self):
        p = self.pos
        out =  ((p[0] - globals.game_view.viewpos._pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos._pos.y)*globals.scale.y,self.z)
        return out

class Torch(ConeLight):
    def __init__(self,parent,offset):
        self.quad_buffer = drawing.QuadBuffer(4)
        self.quad = drawing.Quad(self.quad_buffer)
        self.shadow_quad = globals.shadow_quadbuffer.NewLight()
        self.shadow_index = self.shadow_quad.shadow_index
        self.parent = parent
        self.last_update    = None
        self.colour = (1,1,1)
        self.angle = 0.0
        self.offset = cmath.polar(offset.x + offset.y*1j)
        self.angle_width = 0.7
        self.on = True
        globals.cone_lights.append(self)

    @property
    def world_pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))
        return (pos.x,pos.y,self.z)

    @property
    def pos(self):
        offset = cmath.rect(self.offset[0],self.offset[1]+self.parent.angle)
        pos = (self.parent.pos + Point(offset.real,offset.imag))
        return (pos.x,pos.y,self.z)

    def Update(self,t):
        self.angle = (self.parent.angle + math.pi*0.5)%(2*math.pi)
        box = (globals.tile_scale*Point(self.width,self.height))
        bl = Point(*self.pos[:2]) - box*0.5
        tr = bl + box
        bl = bl.to_int()
        tr = tr.to_int()
        self.quad.SetVertices(bl,tr,4)
        #self.quad.SetAllVertices(self.parent.vertices, 0)

class Boat(Actor):
    texture = 'boat'
    width = 108
    height = 27

    def __init__(self,pos):
        super(Boat,self).__init__(pos)
        #self.light = ActorLight(self)

    def Update(self,t):

        super(Boat,self).Update(t)
        #self.light.Update(t)

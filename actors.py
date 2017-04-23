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

    max_speed = 3
    max_square_speed = max_speed**2
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

    def remove_from_map(self):
        if self.pos != None:
            globals.aabb.remove(self)

    def add_to_map(self):
        globals.aabb.add(self)

    def SetPos(self,pos):
        self.remove_from_map()
        self.pos = pos

        self.vertices = [((pos + corner)) for corner in self.corners_euclid]

        #bl = pos
        #tr = bl + self.size
        #bl = bl.to_int()
        #tr = tr.to_int()
        #self.quad.SetVertices(bl,tr,4)

        self.quad.SetAllVertices(self.vertices, 4)
        self.add_to_map()

    def TriggerCollide(self,other):
        pass

    def set_angle(self, angle):
        self.angle = angle%(2*math.pi)
        self.corners_polar  = [(p.length(),self.angle + self.polar_offsets[i]) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]

    def Update(self,t):
        return self.Move(t)

    def hand_pos(self):
        return self.pos + self.hand_offset.Rotate(self.angle)

    def Move(self,t):

        if self.last_update == None:
            self.last_update = globals.time
            return 0
        elapsed = (globals.time - self.last_update)*globals.time_step
        self.last_update = globals.time

        angle_change = self.angle_speed*elapsed
        self.set_angle(self.angle + angle_change)

        amount = Point(0,0)

        self.move_speed += self.move_direction.Rotate(self.angle)*elapsed
        #self.move_speed += self.move_direction*elapsed
        if self.move_speed.SquareLength() > self.max_square_speed:
            self.move_speed = self.move_speed.unit_vector() * self.max_speed

        #self.move_speed.y -= self.move_speed.y * elapsed

        if self.interacting:
            self.move_speed = Point(0,0)

        amount += self.move_speed * elapsed

        #check for collisions
        for other in globals.aabb.nearby(self):
            #print other.pos,'near',self.pos
            if isinstance(other,Player):
                #handle this separate
                p = self.pos + amount
                probe = p + ((other.pos - p).unit_vector()*self.radius)
                if other.is_inside(probe):
                    self.kill()
                continue


            #All these mobile things are helpfull just little spheres, so collision detection is easy
            distance = other.pos - (self.pos + amount)
            if distance.SquareLength() < self.radius_square + other.radius_square:
                print self,'collided with',other
                t = self.move_speed
                self.move_speed = other.move_speed
                other.move_speed = t
                #self.move_direction = other.move_direction = 0
                #also need to move them so they don't overlap
                overlap = self.radius + other.radius - distance.length()
                adjust = distance.unit_vector()*-overlap
                amount += adjust*0.1

        #if globals.game_view.boat.is_inside(self.pos):
        #    print 'hit boat!'

        self.SetPos(self.pos + amount)
        #self.SetPos(self.pos)
        return elapsed

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
    z = 80
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
        self.radius = 10
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

class SquareActor(Actor):
    collide_centre = Point(0,0)
    def is_inside(self, p):
        #first need to rotate the point so we can do the test
        diff = (p - self.pos).Rotate(-self.angle)
        new_p = self.pos + diff
        bl = self.pos + self.collide_centre - self.collide_size/2
        tr = bl + self.collide_size

        if new_p.x >= bl.x and new_p.x < tr.x:
            if new_p.y >= bl.y and new_p.y < tr.y:
                return True
        return False


class Player(SquareActor):
    texture = 'guy_pipe'
    width = 32
    height = 48
    boat_offset = Point(24,9)
    collide_size = Point(12,24.5).to_float()
    collide_centre = Point(-1,-4)
    def __init__(self, boat):
        self.boat = boat
        super(Player,self).__init__(self.boat.pos + self.boat_offset)

    def Update(self,t):
        self.SetPos(self.boat.pos + self.boat_offset)

class Boat(SquareActor):
    texture = 'boat'
    width = 108
    height = 27
    water_height = 9
    max_speed = 3
    max_square_speed = max_speed**2
    collide_centre = Point(0,-8)
    collide_size = Point(width,height-8)

    def __init__(self,pos,water):
        self.water = water
        super(Boat,self).__init__(Point(pos.x, pos.y + self.water_height))
        #self.light = ActorLight(self)
        #self.SetPos(self.pos)
        #self.Update(0)

    def remove_from_map(self):
        pass

    def add_to_map(self):
        pass

    def Update(self,t):
        elapsed = super(Boat,self).Update(t)
        if not elapsed:
            return
        #we update our angle based on the water height at our ends
        water_height = self.water.get_height(self.pos.x)
        new_pos = water_height + self.water_height

        #print 'md',self.move_direction

        #print 'boat',self.pos.x,self.pos.x+self.size.x, new_pos, self.move_direction
        self.move_direction.y = (new_pos - self.pos.y) * elapsed * 0.5
        #friction for the water
        self.move_speed.x -= self.move_speed.x * 0.2 * elapsed

        front_height = self.water.get_height(self.pos.x + self.size.x/2)
        back_height = self.water.get_height(self.pos.x - self.size.x/2)

        target_angle = cmath.polar(self.size.x + (front_height - back_height)*1j)[1]

        #angle_acc = (target_angle - self.angle) * 0.01
        #print target_angle,self.angle,angle_acc
        #self.angle_speed += angle_acc * elapsed
        self.angle = target_angle

        #self.light.Update(t)

    def Move(self,t):

        if self.last_update == None:
            self.last_update = globals.time
            return 0
        elapsed = (globals.time - self.last_update)*globals.time_step
        self.last_update = globals.time

        angle_change = self.angle_speed*elapsed
        self.set_angle(self.angle + angle_change)

        #self.move_speed += self.move_direction.Rotate(self.angle)*elapsed
        self.move_speed += self.move_direction*elapsed
        if self.move_speed.SquareLength() > self.max_square_speed:
            self.move_speed = self.move_speed.unit_vector() * self.max_speed

        self.move_speed.y -= self.move_speed.y * elapsed
        #print 'bms',self.move_speed.x

        if self.interacting:
            self.move_speed = Point(0,0)

        amount = self.move_speed * elapsed

        self.SetPos(self.pos + amount)
        #self.SetPos(self.pos)
        return elapsed



class Critter(Actor):
    texture = 'basic_critter'
    width = 16
    height = 16
    max_speed = 100
    max_square_speed = max_speed**2

    def __init__(self, pos):
        super(Critter,self).__init__(pos)
        #self.light = ActorLight(self)
        self.activation_length = 2000 + random.random() * 3000
        self.activation_distance = 150 + 200 * random.random()
        self.start_jump = None
        self.jumping = False
        self.splashed = False

    def kill(self):
        globals.aabb.remove(self)
        self.quad.Disable()
        self.quad.Delete()
        self.dead = True

    def Update(self,t):
        #self.light.Update(t)
        boat = globals.game_view.boat
        player = globals.game_view.player
        if self.jumping:
            self.Move(t)
            if not self.splashed and self.pos.y < 60:
                water_height = globals.game_view.water.get_height(self.pos.x)
                if abs(self.pos.y - water_height) < 10:
                    globals.game_view.water.jiggle(self.pos.x, self.move_speed.y)
                    self.splashed = True

                    #print 'ended at',globals.time,boat.pos.x,self.pos.x

            if self.pos.y < 0:
                self.kill()

        if self.start_jump is None:
            distance = player.pos.x - self.pos.x
            if abs(distance) < self.activation_distance:
                self.start_jump = globals.time + self.activation_length
                print 'start jump in',self.activation_length
            #self.start_jump = globals.time
        elif globals.time > self.start_jump and not self.jumping:
            print 'Start jump boom',globals.time
            gravity = -1
            fall_distance = -(self.pos.y - player.pos.y)
            start_speed_y = random.random()*10
            a = gravity
            try:
                fall_time = (math.sqrt(start_speed_y**2 + 2*a*fall_distance) - start_speed_y) / a
            except ValueError:
                fall_time = -1
            x = (-math.sqrt(start_speed_y**2 + 2*a*fall_distance) - start_speed_y) / a

            fall_time = max(fall_time,x)/globals.time_step

            #Their estimate of the fall time should not be perfect
            fall_time = 0.7*fall_time + 0.3*fall_time*random.random()

            #print 'guess at',globals.time + fall_time
            #What position will the boat be in at that time?
            boat_pos_future = player.pos.x + boat.move_speed.x*fall_time*globals.time_step
            #print 'boat_pos guess',boat_pos_future,player.pos.x
            #Now we just need to choose our x speed to arrive there at that time
            distance = boat_pos_future - self.pos.x

            self.move_direction = Point(0,gravity)

            #s = ut + 1/2*a*t*t =>
            start_speed_y = start_speed_y * 0.8 + random.random() * start_speed_y * 0.2

            self.move_speed = Point(distance/(fall_time*globals.time_step),start_speed_y)
            self.jumping = True

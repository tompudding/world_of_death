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

class Dirs:
    RIGHT = 0
    LEFT  = 1

class Actor(object):
    texture = None
    width   = None
    height  = None
    initial_health = 100
    is_player = False
    bounce = False
    level = 4

    max_speed = 3
    max_square_speed = max_speed**2
    bounce_holdoff = 1000
    def __init__(self,pos):
        self.tc             = globals.atlas.TextureSpriteCoords('%s.png' % self.texture)
        self.tc_left        = [self.tc[i] for i in (3,2,1,0)]
        self.quad           = drawing.Quad(globals.quad_buffer,tc = self.tc)
        self.size           = Point(self.width,self.height)
        self.corners = self.size, Point(-self.size.x,self.size.y), Point(-self.size.x,-self.size.y), Point(self.size.x,-self.size.y)
        #that's a weird order
        self.corners = [self.corners[2],self.corners[1],self.corners[0],self.corners[3]]
        self.corners        = [p*0.5 for p in self.corners]
        #self.corners_polar  = [(p.length(),((1+i*2)*math.pi)/4) for i,p in enumerate(self.corners)]
        self.polar_offsets = [cmath.polar(p.x+p.y*1j)[1] for p in self.corners]
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
        self.bounce_allowed = 0
        self.dir = Dirs.RIGHT
        self.on_boat = False
        self.been_hit = False
        self.snacking = False

        self.set_angle(0)

        self.hand_offset = Point(0,self.size.y*1.1)
        self.track_quads = []
        self.last_track = 0


    def kill(self):
        globals.aabb.remove(self)
        if self.snacking:
            globals.sounds.chomp.stop()
        self.quad.Disable()
        self.quad.Delete()
        self.dead = True

    def possible_collision(self, other, amount):
        pass

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
        if self.dead:
            return
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

        self.quad.SetAllVertices(self.vertices, self.level)
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
            self.possible_collision(other, amount)

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
        p = (self.pos - globals.game_view.viewpos.full_pos)*globals.scale
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
        return ((p[0] - globals.game_view.viewpos.full_pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos.full_pos.y)*globals.scale.y,self.z)

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
        out =  ((p[0] - globals.game_view.viewpos.full_pos.x)*globals.scale.x,(p[1]-globals.game_view.viewpos.full_pos.y)*globals.scale.y,self.z)
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
    collide_centre = [Point(0,0),Point(0,0)]
    def is_inside(self, p):
        #first need to rotate the point so we can do the test
        diff = (p - self.pos).Rotate(-self.angle)
        new_p = self.pos + diff
        bl = self.pos + self.collide_centre[self.dir] - self.collide_size[self.dir]/2
        tr = bl + self.collide_size[self.dir]

        if new_p.x >= bl.x and new_p.x < tr.x:
            if new_p.y >= bl.y and new_p.y < tr.y:
                return True
        return False

class Brolly(SquareActor):
    texture = 'brolly_open'
    arm_offset = [Point(-4,4),Point(3,4)]
    width = 31
    height = 37
    collide_centre = [Point(0,12),Point(0,12)]
    collide_size = [Point(31,12),Point(31,12)]
    rotate_centre = Point(0,18)
    bounce = True

    def __init__(self, person):
        self.person = person
        super(Brolly,self).__init__(self.person.pos + self.arm_offset[Dirs.RIGHT])
        self.swinging = False
        self.open_tc = self.tc
        self.closed_tc = globals.atlas.TextureSpriteCoords('brolly_closed.png')
        self.tc = self.closed_tc
        self.murder = False

    def put_up(self):
        self.up = True
        self.quad.SetTextureCoordinates(self.open_tc)
        self.quad.Enable()
        self.level = 3.5
        globals.sounds.brolly_open.play()

    def put_down(self):
        self.up = False
        self.quad.Disable()

    def prepare_swing(self):
        self.swinging = True
        self.quad.SetTextureCoordinates(self.closed_tc)
        self.quad.Enable()
        self.level = 5

    def swing(self):
        self.swinging = False

    def start_murder(self):
        self.murder = True

    def do_murder(self):
        #We've just swung the brolly like a bat. Let's check if there are any critters to squish
        tip = self.pos + (self.rotate_centre).Rotate(self.angle)
        hits = False
        for critter in globals.aabb.nearby(self):
            if critter is self.person:
                continue
            #There are two points of interest; the tip and base of the brolly. Anything too close to those
            #or the line that joins them are in for a bad time

            #If we rotate the critter pos by the inverse of our angle we can do a simple rectangle check
            #for if it's near our line
            diff = critter.pos - self.pos
            v = diff.Rotate(-self.angle)
            print 'maybe hit',v
            if abs(v.x) > 15:
                #out of range
                continue
            if abs(v.y) > 25:
                continue
            #print 'hit',diff
            #Send this guy flying in the direction we swung
            #thrust = cmath.rect(-10,self.angle + math.pi*0.5)
            critter.move_speed.x += (diff.unit_vector().x * 15)
            #always knock them up for fun
            critter.move_speed.y += 10
            #renable gravity if it were turned off
            critter.move_direction = Point(0,-1)
            critter.been_hit = True
            hits = True
        if hits:
            globals.sounds.donk.play()



    def finish_swinging(self):
        self.quad.Disable()

    def Update(self,t,angle_to_mouse):
        if self.up or not self.swinging:
            self.set_angle(angle_to_mouse)
        elif self.swinging:
            self.set_angle(angle_to_mouse + math.pi)
        #we also want to move it such that the arm thing stays in the same place
        extra = self.rotate_centre.Rotate(self.angle)

        self.SetPos(self.person.pos + self.arm_offset[self.person.dir] + extra)
        if self.murder:
            self.murder = False
            self.do_murder()

class Player(SquareActor):
    texture = 'guy_pipe'
    width = 32
    height = 48
    boat_offset_right = Point(24,9)
    boat_offset_left = Point(17,9)
    collide_size = [Point(8,24.5).to_float(),Point(8,24.5).to_float()]
    collide_centre = [Point(-2,0),Point(4,0)]
    approx_boat_offset = Point(20,13)
    is_player = True
    brolly_up_time = 100
    brolly_down_time = 100
    brolly_swing_time = 400
    immune_duration = 0
    min_swing = 200

    class Status:
        BROLLY_UP = 0
        BROLLY_DOWN = 1
        BROLLY_SWING = 2

    def __init__(self, boat):
        self.boat = boat
        self.boat_offset = self.boat_offset_right
        super(Player,self).__init__(self.boat.pos + self.boat_offset)

        tc_brolly = globals.atlas.TextureSpriteCoords('guy_nothing.png')
        tc_brolly_left = [tc_brolly[i] for i in (3,2,1,0)]
        tc_brolly_swing = globals.atlas.TextureSpriteCoords('guy_swing.png')
        tc_brolly_swing_left = [tc_brolly_swing[i] for i in (3,2,1,0)]
        self.status = Player.Status.BROLLY_DOWN
        self.target_status = self.status
        self.tc = { Player.Status.BROLLY_UP    : [tc_brolly,tc_brolly_left],
                    Player.Status.BROLLY_DOWN  : [self.tc, self.tc_left],
                    Player.Status.BROLLY_SWING : [tc_brolly_swing,tc_brolly_swing_left] }

        self.brolly = Brolly(self)
        self.brolly.put_down()
        self.snackers = []

    def damage(self, amount):
        super(Player,self).damage(amount)
        globals.game_view.health_display.set_health(float(self.health) / self.initial_health)
        globals.game_view.viewpos.ScreenShake(amount, 400)

    def Death(self):
        globals.game_view.GameOver()

    def add_snacking(self, critter):
        self.snackers.append(critter)

    def Update(self,t):

        if self.target_status != self.status:
            #we want to change!
            if globals.time > self.brolly_change_time:

                if self.target_status == Player.Status.BROLLY_UP:
                    if globals.game_view.tutorial == globals.game_view.tutorial_open_brolly:
                        globals.game_view.tutorial()
                        pass
                    self.brolly.put_up()
                elif self.target_status == Player.Status.BROLLY_DOWN:
                    self.brolly.put_down()

                self.status = self.target_status

                self.quad.SetTextureCoordinates(self.tc[self.status][self.dir])

        diff = globals.mouse_world - (self.boat.pos + self.approx_boat_offset)
        r,a = cmath.polar(diff.x + diff.y*1j)
        a += math.pi*1.5
        if globals.mouse_world.x > self.boat.pos.x + self.approx_boat_offset.x:
            if self.dir == Dirs.LEFT:
                self.boat_offset = self.boat_offset_right
                self.dir = Dirs.RIGHT
                self.quad.SetTextureCoordinates(self.tc[self.status][self.dir])

        else:
            if self.dir == Dirs.RIGHT:
                self.dir = Dirs.LEFT
                self.boat_offset = self.boat_offset_left
                self.quad.SetTextureCoordinates(self.tc[self.status][self.dir])

        self.SetPos(self.boat.pos + self.boat_offset)
        self.brolly.Update(t,a)

    def put_brolly_up(self):
        if self.status != Player.Status.BROLLY_DOWN:
            return
        #we've currently got it down but we want it up
        if self.target_status == Player.Status.BROLLY_UP:
            #we already tried to put it up in the past, this will be handled in update
            return

        #We need to record that the player wants it up
        self.target_status = Player.Status.BROLLY_UP
        self.brolly_change_time = globals.time + self.brolly_up_time

        # self.status = Player.Status.BROLLY_UP


    def put_brolly_down(self):
        if self.status != Player.Status.BROLLY_UP:
            if self.target_status != Player.Status.BROLLY_DOWN:
                self.target_status = Player.Status.BROLLY_DOWN
            return
        #we've currently got it down but we want it up
        if self.target_status == Player.Status.BROLLY_DOWN:
            #we already tried to put it up in the past, this will be handled in update
            return
        self.target_status = Player.Status.BROLLY_DOWN
        self.brolly_change_time = globals.time + self.brolly_down_time

    def prepare_brolly_swing(self):
        if any((s == Player.Status.BROLLY_UP for s in (self.status, self.target_status))):
            return
        #Prepare
        self.brolly.prepare_swing()
        self.target_status = self.status = Player.Status.BROLLY_SWING
        self.quad.SetTextureCoordinates(self.tc[self.status][self.dir])
        self.prepare_start = globals.time
        globals.sounds.swing_start.play()

    def swing_brolly(self):
        if self.status != Player.Status.BROLLY_SWING:
            return
        if self.brolly.swinging:
            self.brolly.swing()
        if globals.time - self.prepare_start < self.min_swing:
            self.status = Player.Status.BROLLY_DOWN
            self.target_status = self.status
            self.quad.SetTextureCoordinates(self.tc[self.status][self.dir])
            self.brolly.finish_swinging()
            return
        globals.sounds.swing_end.play()
        self.target_status = Player.Status.BROLLY_DOWN
        self.brolly_change_time = globals.time + self.brolly_swing_time
        self.brolly.start_murder()
        print globals.game_view.tutorial == globals.game_view.tutorial_swing_brolly
        if globals.game_view.tutorial == globals.game_view.tutorial_swing_brolly:
            globals.game_view.tutorial()
        #At this point we can kill anything snacking on us
        for critter in self.snackers:
            critter.kill()
        self.snackers = []
        #self.quad.SetTextureCoordinates(self.tc[self.status][self.dir])

class Boat(SquareActor):
    texture = 'boat'
    width = 108
    height = 27
    water_height = 9
    max_speed = 3
    max_square_speed = max_speed**2
    collide_size = [Point(width,height-8),Point(width,height-8)]
    collide_centre = [Point(0,-8),Point(0,-8)]
    level = 6
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
    snacking_time = 4000
    snack_damage = 2

    def __init__(self, pos):
        super(Critter,self).__init__(pos)
        #self.light = ActorLight(self)
        self.activation_length = 2000 + random.random() * 3000
        self.activation_distance = 50 + 150 * random.random()
        self.start_jump = None
        self.jumping = False
        self.splashed = False
        self.on_boat = False
        self.done_snacking = 0
        self.start_snacking = 0
        self.snacking = False
        self.snacking_tc = globals.atlas.TextureSpriteCoords('critter_snack.png')
        self.snack_pos = 0

    def possible_collision(self, other, amount):
        if other.is_player:
            #handle this separate
            if self.been_hit:
                #we can't hurt the player if we've been hit
                return
            p = self.pos + amount
            #p = self.pos
            #probe = p + ((other.pos - p).unit_vector()*self.radius)
            probe = self.pos
            if other.is_inside(probe):
                self.snacking = True
                self.done_snacking = globals.time + self.snacking_time
                self.start_snacking = globals.time
                self.player_offset = self.pos - other.pos
                other.add_snacking(self)
            return

        if self.dead or other.dead:
            return

        if other.bounce:
            #if other.up and globals.time > self.bounce_allowed and not self.on_boat:
            if other.up and not self.on_boat:
                #we should bounce off this
                p = self.pos + amount
                diff = other.pos - p
                diff_uv = diff.unit_vector()
                probe = p + (diff_uv*self.radius)
                if other.is_inside(probe):
                    #What angle will we send the critter off at? take the brolly as a circle
                    #and ping it off at the normal
                    self.move_speed = (diff_uv * self.move_speed.length())*-1
                    self.bounce_allowed = globals.time + self.bounce_holdoff
                    globals.sounds.bounce.play()
            return

        #All these mobile things are helpfull just little spheres, so collision detection is easy
        distance = other.pos - (self.pos + amount)
        if distance.SquareLength() < self.radius_square + other.radius_square and not self.snacking and not other.snacking:
            t = self.move_speed
            self.move_speed = other.move_speed
            other.move_speed = t
            #self.move_direction = other.move_direction = 0
            #also need to move them so they don't overlap
            overlap = self.radius + other.radius - distance.length()
            adjust = distance.unit_vector()*-overlap
            amount += adjust*0.1


    def Update(self,t):
        #self.light.Update(t)
        if self.dead:
            return
        boat = globals.game_view.boat
        player = globals.game_view.player
        if self.snacking:

            if globals.time > self.done_snacking:
                globals.sounds.chomp.stop()
                self.kill()
                return

            elapsed = globals.time - self.start_snacking
            self.SetPos(player.pos + self.player_offset)
            #Move it up and down
            if (elapsed % 200) > 100:
                if self.snack_pos == 0:
                    vertices = [v + Point(0,2) for v in self.vertices]
                    player.damage(self.snack_damage)

                    self.snack_pos = 1
                else:
                    vertices = self.vertices
            else:
                vertices = self.vertices
                self.snack_pos = 0
            self.quad.SetAllVertices(vertices, self.level)
            self.quad.SetTextureCoordinates(self.snacking_tc)
            return

        if self.jumping:
            if not self.on_boat:
                self.Move(t)
                if boat.is_inside(self.pos) and not self.been_hit:
                    globals.game_view.water.jiggle(self.pos.x, self.move_speed.y/4)
                    self.on_boat = True
                    globals.sounds.thunk.play()
                    self.boat_offset = self.pos - boat.pos
                    self.move_speed = Point( ((player.pos - self.pos).unit_vector() * 2).x,0)
                    self.move_direction = Point(0,0)

                    self.splashed = True
            elif not self.been_hit:
                #We're on the boat!
                #let's walk towards the player
                #elapsed = (globals.time - self.last_update)*globals.time_step
                #self.last_update = globals.time
                #player_dir = (player.pos - self.pos).unit_vector() * 0.1 * elapsed
                #self.boat_offset += player_dir
                #self.SetPos(boat.pos + self.boat_offset)
                self.Move(t)
                if self.move_speed.x > 0:
                    past = self.pos.x > player.pos.x
                else:
                    past = self.pos.x < player.pos.x
                if past and not self.snacking and not self.been_hit and (self.pos - player.pos).length() < 20:
                    #we're on the boat and not snacking after going past the player, likely this is a bug,
                    #so hax!
                    self.snacking = True
                    self.done_snacking = globals.time + self.snacking_time
                    self.start_snacking = globals.time
                    globals.sounds.chomp.play()
                    self.player_offset = self.pos - player.pos
                    player.add_snacking(self)

                if self.pos.y > 80:
                    self.splashed = False
            else:
                self.move_direction = Point(0,-1)
                self.Move(t)
                if self.pos.y > 80:
                    self.splashed = False

            if self.dead:
                return

            if not self.splashed and self.pos.y < 60:
                water_height = globals.game_view.water.get_height(self.pos.x)
                if abs(self.pos.y - water_height) < 10:
                    globals.sounds.splash.play()
                    globals.game_view.water.jiggle(self.pos.x, self.move_speed.y)
                    self.splashed = True

                    #print 'ended at',globals.time,boat.pos.x,self.pos.x

            if self.pos.y < 0:
                self.kill()

        if self.start_jump is None:
            distance = player.pos.x - self.pos.x
            if abs(distance) < self.activation_distance:
                self.start_jump = globals.time + self.activation_length

            #self.start_jump = globals.time
        elif globals.time > self.start_jump and not self.jumping:

            #player = boat
            boat_back = boat.pos - boat.size/2
            boat_front = boat.pos + boat.size/2
            target = random.choice([boat_back, player.pos, boat_front])
            gravity = -1
            fall_distance = -(self.pos.y - target.y)
            start_speed_y = random.random()*10
            a = gravity
            try:
                fall_time = (math.sqrt(start_speed_y**2 + 2*a*fall_distance) - start_speed_y) / a
            except ValueError:
                fall_time = -1
            x = (-math.sqrt(start_speed_y**2 + 2*a*fall_distance) - start_speed_y) / a

            fall_time = max(fall_time,x)/globals.time_step

            #Their estimate of the fall time should not be perfect
            #fall_time = 0.7*fall_time + 0.3*fall_time*random.random()

            #print 'guess at',globals.time + fall_time
            #What position will the boat be in at that time?
            boat_pos_future = target.x + boat.move_speed.x*fall_time*globals.time_step
            #print 'boat_pos guess',boat_pos_future,player.pos.x
            #Now we just need to choose our x speed to arrive there at that time
            distance = boat_pos_future - self.pos.x

            self.move_direction = Point(0,gravity)

            #s = ut + 1/2*a*t*t =>
            #start_speed_y = start_speed_y * 0.8 + random.random() * start_speed_y * 0.2

            self.move_speed = Point(distance/(fall_time*globals.time_step),start_speed_y)
            self.jumping = True
            random.choice(globals.sounds.wee_sounds).play()

class Arrow(Actor):
    texture = 'arrow'
    width = 6
    height = 16
    max_speed = 100
    max_life = 10000
    max_square_speed = max_speed**2
    damage_amount = 10

    def __init__(self, parent, pos, dir, speed):
        super(Arrow,self).__init__(pos)
        self.parent = parent
        self.move_direction = dir
        self.move_speed = speed
        self.stuck = False
        self.real_angle = 0

    def possible_collision(self, other, amount):
        if self.stuck:
            return
        if other.is_player:
            #handle this separate
            if self.been_hit:
                #we can't hurt the player if we've been hit
                return
            p = self.pos + amount
            #p = self.pos
            #probe = p + ((other.pos - p).unit_vector()*self.radius)
            probe = self.pos
            if other.is_inside(probe):
                self.stuck = other
                self.stuck_offset = self.pos - other.pos
                self.die_time = globals.time + self.max_life
                other.damage(self.damage_amount)
                globals.sounds.arrow_hit.play()
            return

        if other.bounce:
            if other.up:
                p = self.pos + amount
                diff = other.pos - p
                diff_uv = diff.unit_vector()
                #probe = p + (diff_uv*self.radius)
                probe = self.pos
                if other.is_inside(probe):
                    self.stuck = other
                    self.die_time = globals.time + self.max_life
                    self.stuck_angle = self.real_angle - other.angle
                    self.stuck_offset = (self.pos - other.pos).Rotate(-self.real_angle)
                    globals.sounds.arrow_stick.play()

    def Update(self, t):
        if self.stuck:
            so = self.stuck_offset
            if self.stuck.bounce and self.stuck.up:
                #We need to rotate ourselves around the brolly
                self.set_angle(self.stuck.angle + self.stuck_angle)
                #now just update the position
                so = self.stuck_offset.Rotate(self.stuck.angle + self.stuck_angle)

            if globals.time > self.die_time or (self.stuck.bounce and not self.stuck.up):
                self.kill()
            self.SetPos(self.stuck.pos + so)
            return
        super(Arrow,self).Update(t)
        r,a = cmath.polar(self.move_speed.x + self.move_speed.y*1j)
        a = (a + math.pi*1.5)%(2*math.pi)
        self.real_angle = a
        self.corners_polar  = [(p.length(),a + self.polar_offsets[i]) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]
        self.SetPos(self.pos)
        if self.pos.y < 0:
            self.kill()


class Rock(Actor):
    texture = 'rock'
    width = 8
    height = 8
    max_speed = 100
    max_life = 10000
    max_square_speed = max_speed**2
    damage_amount = 8

    def __init__(self, parent, pos, dir, speed):

        super(Rock,self).__init__(pos)
        self.parent = parent
        self.move_direction = dir
        self.move_speed = speed
        self.splashed = False
        self.real_angle = 0

    def possible_collision(self, other, amount):
        if other.is_player:
            #handle this separate

            #p = self.pos + amount
            #p = self.pos
            #probe = p + ((other.pos - p).unit_vector()*self.radius)
            probe = self.pos
            if other.is_inside(probe):
                self.kill()
                other.damage(self.damage_amount)
            return

        if other.bounce:
            if other.up and globals.time > self.bounce_allowed:
                p = self.pos + amount
                diff = other.pos - p
                diff_uv = diff.unit_vector()
                #probe = p + (diff_uv*self.radius)
                probe = self.pos
                if other.is_inside(probe):
                    self.move_speed = (diff_uv * self.move_speed.length())*-1
                    self.bounce_allowed = globals.time + self.bounce_holdoff

    def Update(self, t):
        elapsed = super(Rock,self).Update(t)

        if not self.splashed and self.pos.y < 60:
            water_height = globals.game_view.water.get_height(self.pos.x)
            if abs(self.pos.y - water_height) < 10:
                globals.game_view.water.jiggle(self.pos.x, self.move_speed.y*0.1)
                self.splashed = True

        if self.pos.y < 0:
            self.kill()

        self.real_angle += elapsed * 0.5
        self.corners_polar  = [(p.length(),self.real_angle + self.polar_offsets[i]) for i,p in enumerate(self.corners)]
        cnums = [cmath.rect(r,a) for (r,a) in self.corners_polar]
        self.corners_euclid = [Point(c.real,c.imag) for c in cnums]
        self.SetPos(self.pos)

class Drop(Actor):
    texture = 'drop'
    width = 8
    height = 8
    max_speed = 100
    max_life = 10000
    max_square_speed = max_speed**2
    damage_amount = 0
    jiggle_amount = 0.04

    def __init__(self, parent, pos, dir, speed):

        super(Drop,self).__init__(pos)
        self.parent = parent
        self.move_direction = dir
        self.move_speed = speed
        self.splashed = False
        self.real_angle = 0

    def possible_collision(self, other, amount):
        if other.is_player:
            #handle this separate

            #p = self.pos + amount
            #p = self.pos
            #probe = p + ((other.pos - p).unit_vector()*self.radius)
            probe = self.pos
            if other.is_inside(probe):
                self.kill()
            return

        if other.bounce:
            if other.up:
                probe = self.pos
                if other.is_inside(probe):
                    self.kill()


    def Update(self, t):
        elapsed = super(Drop,self).Update(t)

        if not self.splashed and self.pos.y < 60:
            water_height = globals.game_view.water.get_height(self.pos.x)
            if abs(self.pos.y - water_height) < 10:
                globals.game_view.water.jiggle(self.pos.x, self.move_speed.y*self.jiggle_amount)
                self.splashed = True

        if self.pos.y < 0:
            self.kill()


class BowCritter(Critter):
    shooting_range = 300
    fire_cooldown = 2000

    def __init__(self, pos):
        super(BowCritter, self).__init__(pos)
        self.fire_time = 0

    def possible_collision(self, other, amount):
        if other.bounce:
            if other.up:
                p = self.pos + amount
                diff = other.pos - p
                diff_uv = diff.unit_vector()
                probe = p + (diff_uv*self.radius)
                if other.is_inside(probe):
                    #What angle will we send the critter off at? take the brolly as a circle
                    #and ping it off at the normal
                    self.move_speed = (diff_uv * self.move_speed.length())*-1
                    self.move_direction = Point(0,-1)


    def Update(self,t):
        if self.dead:
            return
        boat = globals.game_view.boat
        player = globals.game_view.player

        self.Move(t)

        if self.pos.x < globals.game_view.viewpos.pos.x - 20:
            self.kill()
            return

        distance = player.pos.x - self.pos.x
        if abs(distance) < self.shooting_range and globals.time > self.fire_time:
            #player = boat
            target = player.pos
            gravity = -1
            fall_distance = -(self.pos.y - target.y)
            start_speed_y = -5 + random.random()*10
            a = gravity
            try:
                fall_time = (math.sqrt(start_speed_y**2 + 2*a*fall_distance) - start_speed_y) / a
            except ValueError:
                fall_time = -1
            try:
                x = (-math.sqrt(start_speed_y**2 + 2*a*fall_distance) - start_speed_y) / a
            except ValueError:
                return

            fall_time = max(fall_time,x)/globals.time_step

            #What position will the boat be in at that time?
            boat_pos_future = target.x + boat.move_speed.x*fall_time*globals.time_step
            #print 'boat_pos guess',boat_pos_future,player.pos.x
            #Now we just need to choose our x speed to arrive there at that time
            distance = boat_pos_future - self.pos.x

            arrow = Arrow(self, pos=self.pos, dir = Point(0,gravity), speed = Point(distance/(fall_time*globals.time_step),start_speed_y))
            globals.game_view.arrows.append(arrow)
            self.fire_time = globals.time + self.fire_cooldown

class RockCritter(BowCritter):
    fire_cooldown = 1000
    object_class = Rock

    def __init__(self, pos):
        super(BowCritter, self).__init__(pos)
        self.fire_time = None

    def Update(self,t):
        if self.dead:
            return

        if self.fire_time is None:
            self.fire_time = globals.time + random.random()*self.fire_cooldown

        self.Move(t)

        if self.pos.x < globals.game_view.viewpos.pos.x or self.pos.x > globals.game_view.viewpos.pos.x + globals.screen_showing.x:
            return

        if globals.time > self.fire_time:
            #We just drop a rock

            rock = self.object_class(self, pos=self.pos, dir = Point(0,-1), speed = Point(0,0))
            globals.game_view.arrows.append(rock)
            self.fire_time = globals.time + self.fire_cooldown


class DropCritter(RockCritter):
    object_class = Drop
    fire_cooldown = 1000

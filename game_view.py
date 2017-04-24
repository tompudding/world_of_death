from OpenGL.GL import *
import random,numpy,cmath,math,pygame

import ui,globals,drawing,os,copy
from globals.types import Point
import modes
import random
import actors

class ViewPos(object):
    shake_radius = 10
    def __init__(self, pos):
        self.pos = pos
        self.shake_end = None
        self.shake_duration = 1
        self.shake = Point(0,0)
        self.last_update = None

    def ScreenShake(self,radius,duration):
        self.shake_end = globals.time + duration
        self.shake_radius = radius
        self.shake_duration = float(duration)

    def reset(self):
        self.shake_end = None

    @property
    def full_pos(self):
        return self.pos + self.shake

    def Update(self):
        if self.last_update is None:
            self.last_update = globals.time
            return
        elapsed = (globals.time - self.last_update) * globals.time_step
        self.last_update = globals.time

        if self.shake_end:
            if globals.time >= self.shake_end:
                self.shake_end = None
                self.shake = Point(0,0)
            else:
                left = (self.shake_end - globals.time)/self.shake_duration
                radius = left*self.shake_radius
                self.shake = Point(random.random()*radius,random.random()*radius)

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
    k = 0.1
    damping = 0.025
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
    spread = 0.01
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

        try:
            left_height = self.springs[i].top.y
            right_height = self.springs[j].top.y
        except IndexError:
            return 0

        return left_height + (right_height - left_height) * partial

    def jiggle(self, x, amount):
        n = int((x - self.left)/self.spacing)

        try:
            self.springs[n].velocity += amount
        except IndexError:
            pass


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

class BoundingBox(object):
    def __init__(self):
        self.actors = {}

    def add(self, actor):
        self.actors[actor] = True

    def remove(self, actor):
        try:
            del self.actors[actor]
        except KeyError:
            pass

class AxisAlignedBoundingBoxes(object):
    box_size = 16
    def __init__(self, viewpos):
        self.viewpos = viewpos
        self.grid = []
        for x in xrange(0, globals.screen_showing.x, self.box_size):
            col = []
            for y in xrange(0, globals.screen_showing.y, self.box_size):
                col.append(BoundingBox())
            self.grid.append(col)
        self.locations_per_actor = {}

    def add(self, actor):
        ap = actor.pos - self.viewpos.pos
        bl = (ap / self.box_size).to_int()
        tr = ((ap + actor.size) / self.box_size).to_int()

        for x in xrange(bl.x, tr.x + 1):
            for y in xrange(bl.y, tr.y + 1):
                try:
                    self.grid[x][y].add(actor)
                except IndexError:
                    continue
                try:
                    self.locations_per_actor[actor].append( (x,y) )
                except KeyError:
                    self.locations_per_actor[actor] = [ (x,y) ]

    def remove(self, actor):
        try:
            for x,y in self.locations_per_actor[actor]:
                self.grid[x][y].remove(actor)
        except KeyError:
            pass
        self.locations_per_actor[actor] = []

    def nearby(self, actor):
        #return all the actors that share locations with the given actor
        if actor not in self.locations_per_actor:
            return []
        out = set()
        for x,y in self.locations_per_actor[actor]:
            for other in self.grid[x][y].actors:
                if other is not actor:
                    out.add(other)
        return out

class GameView(ui.RootElement):
    water_height = 40
    light_spacing = 250
    light_height = 150
    def __init__(self):
        self.atlas = globals.atlas = drawing.texture.TextureAtlas('tiles_atlas_0.png','tiles_atlas.txt')
        globals.ui_atlas = drawing.texture.TextureAtlas('ui_atlas_0.png','ui_atlas.txt',extra_names=False)
        self.enemies = []
        #globals.ui_atlas = drawing.texture.TextureAtlas('ui_atlas_0.png','ui_atlas.txt',extra_names=False)
        self.viewpos = ViewPos(Point(0,0))
        globals.aabb = AxisAlignedBoundingBoxes(self.viewpos)
        #Make a big background. Making it large lets opengl take care of the texture coordinates
        #TODO: tie this in with the size of the map
        self.background = Background('tile')
        self.water = Water(parent = self, height = self.water_height)
        self.health_display = ui.Hearts(parent = globals.screen_root,
                                        pos = Point(0.02,0.04),
                                        full_tc = globals.ui_atlas.TextureUiCoords('hearts_full.png'),
                                        empty_tc = globals.ui_atlas.TextureUiCoords('hearts_empty.png'),
                                        buffer = globals.screen_texture_buffer)
        self.tutorial_text = ui.TextBox(parent = globals.screen_root,
                                        bl = Point(0.6,0),
                                        tr = Point(1.0,0.15),
                                        text = 'Welcome! Please keep your hands inside the boat at all times. Don\'t for instance press the left mouse button to swing your brolly',
                                        colour = (1,1,1,1),
                                        scale = 6)
        self.help_text = ui.TextBox(parent = globals.screen_root,
                                    bl = Point(0.4,0),
                                    tr = Point(1,0.05),
                                    text = 'ESC to skip tutorial',
                                    colour = (1,1,1,1),
                                    scale = 6)
        self.game_over_frame = ui.UIElement(parent = globals.screen_root,
                                            pos = Point(0.35,0.3),
                                            tr = Point(0.75,0.7))
        self.game_over_frame.title = ui.TextBox(parent = self.game_over_frame,
                                                bl = Point(0.1,0),
                                                tr = Point(0.9,0.9),
                                                text = 'GAME OVER',
                                                colour = (0.9,0.4,0.4,1),
                                                scale = 36)
        self.game_over_frame.help = ui.TextBox(parent = self.game_over_frame,
                                               bl = Point(-0.62,0),
                                               tr = None,
                                               text = 'Press R to restart level or ESC to start over',
                                               colour = (0.9,0.4,0.4,1),
                                               scale = 12)

        self.game_over_frame.Disable()


        self.game_over = False
        self.mouse_world = Point(0,0)
        self.mouse_pos = Point(0,0)
        pygame.mixer.music.load(os.path.join(globals.dirs.sounds,'sw_normal.ogg'))
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

        self.timeofday = TimeOfDay(0.5)
        self.mode = modes.GameMode(self)
        self.StartMusic()
        #self.fixed_light = actors.FixedLight( Point(11,38),Point(26,9) )
        self.text_colour = (0,1,0,1)

        #self.map = GameMap('level1.txt',self)
        self.mode = modes.GameMode(self)
        #self.map.world_size = self.map.size * globals.tile_dimensions
        self.boat = actors.Boat(Point(globals.screen_showing.x /2 ,self.water_height), self.water)
        self.boat.move_direction = Point(0.7,0)
        self.player = actors.Player(self.boat)

        self.critters = []
        self.arrows = []
        self.tutorial = self.tutorial_swing_brolly
        self.water_critters = []
        self.water_range = None
        self.flicker_start = None
        self.last_flicker_period = 0
        self.text_end = None

        self.next_level = self.level_one
        self.last_level = self.level_one
        self.level_end = None
        self.level_start_health = 100
        self.won = False

        return
        #generate randomly for ther region 500 -> 1500
        for i in xrange(20):

            x = 500 + random.random()*800
            y = 120 + random.random()*120
            pos = Point(x,y)
            while any( ((pos - critter.pos).length() < 20) for critter in self.critters):
                print 'skipping critter at',pos
                x = 500 + random.random()*800
                y = 120 + random.random()*120
                pos = Point(x,y)
            print 'chose critter',pos
            self.critters.append(actors.Critter(pos))

        self.critters.append(actors.BowCritter(Point(400,120)))
        for i in xrange(10):
            self.critters.append(actors.RockCritter(Point(600+i*16,120)))

    def reset(self):
        for c in self.critters:
            c.kill()
        self.critters = []
        self.viewpos.reset()


    def tutorial_swing_brolly(self):
        self.tutorial_text.SetText('Oh my, please dont do that sir. In fact it may get wet soon so you\'ll need to open your brolly with the right mouse button')
        self.water_range = self.viewpos.pos.x + globals.screen_showing.x
        space = 4
        for i in xrange(20):
            critter = actors.DropCritter(Point(self.water_range+i*space,globals.screen_showing.y + 10))
            self.critters.append(critter)
            self.water_critters.append(critter)
        self.water_range += space*len(self.water_critters)
        self.tutorial = self.tutorial_open_brolly

    def tutorial_open_brolly(self):
        self.tutorial_text.SetText(' ')
        self.tutorial = False
        self.help_text.SetText(' ')

    def StartMusic(self):
        #globals.sounds.stop_talking()
        #globals.sounds.talking_intro.play()
        pygame.mixer.music.play(-1)
        pygame.mixer.music.set_volume(globals.music_volume)
        self.music_playing = True

    def Draw(self):
        drawing.ResetState()
        drawing.Translate(-self.viewpos.full_pos.x,-self.viewpos.full_pos.y,0)
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

        if self.text_end and globals.time > self.text_end:
            self.tutorial_text.SetText(' ')
            self.text_end = None

        if self.flicker_start:
            if globals.time > self.flicker_end:
                #we're done
                self.timeofday.Set(0.3)
                for light in globals.lights:
                    light.on = True
                self.flicker_start = None
            else:
                period = (globals.time - self.flicker_start) / 400
                if period != self.last_flicker_period:
                    self.last_flicker_period = period
                    for light in globals.lights:
                        light.on = random.random() < 0.3
                    self.timeofday.Set(random.choice((0,0.28)))

        if self.water_range and self.water_range < self.viewpos.pos.x and not self.tutorial:
            #End of the tutorial
            self.level_start_health = self.player.health
            self.last_level = self.next_level
            self.next_level()

        if self.level_end and self.boat.pos.x > self.level_end or (not self.tutorial and len(self.critters) == 0):
            print 'end of level!'
            self.level_start_health = self.player.health
            self.last_level = self.next_level
            self.next_level()

        self.t = t
        self.water.Update()
        self.boat.Update(t)
        self.player.Update(t)
        for critter in self.critters:
            critter.Update(t)
        self.critters = [critter for critter in self.critters if not critter.dead]

        for arrow in self.arrows:
            arrow.Update(t)
        self.arrows = [arrow for arrow in self.arrows if not arrow.dead]

        self.viewpos.pos.x = self.boat.pos.x - globals.screen_showing.x/2
        self.viewpos.Update()

        if int((self.viewpos.pos.x - self.lights_start)/self.light_spacing) >= 1:
            #move the first to the last
            self.lights_start += self.light_spacing
            self.room_lights = self.room_lights[1:] + self.room_lights[:1]

            self.room_lights[-1].set_pos( Point(self.lights_start + (len(self.room_lights)-1)*self.light_spacing,self.light_height) )

        globals.mouse_world = self.viewpos.pos + self.mouse_pos
        #print globals.mouse_world, self.player.is_inside(globals.mouse_world)
        #print 'mw:',globals.mouse_world

    def level_one(self):
        #Put in some sparse basic baddies
        self.water_range = None
        for c in self.water_critters:
            c.kill()
        self.water_critters = []
        self.music_playing = False
        pygame.mixer.music.set_volume(0)
        globals.sounds.sw_bad_one.play()

        self.tutorial_text.SetText('It\'s ... a .. Smmmaaaaallll')
        self.text_end = globals.time + 2000
        self.boat.move_direction = Point(0.2,0)
        for light in globals.lights:
            light.on = False
            self.timeofday.Set(0.0)
            self.flicker_start = globals.time
            self.flicker_end = globals.time + 4000

        x_0 = self.viewpos.pos.x + globals.screen_showing.x
        self.critters.append(actors.Critter(Point(x_0, 180)))

        for i in xrange(10):
            x = x_0 + random.random()*800
            y = 120 + random.random()*120
            pos = Point(x,y)
            while any( ((pos - critter.pos).length() < 20) for critter in self.critters):
                #print 'skipping critter at',pos
                x = x_0 + random.random()*800
                y = 120 + random.random()*120
                pos = Point(x,y)
            #print 'chose critter',pos
            self.critters.append(actors.Critter(pos))
        self.level_end = x_0 + 800
        self.next_level = self.level_two

    def level_two(self):

        x_0 = self.viewpos.pos.x + globals.screen_showing.x
        for i in xrange(10):
            self.critters.append(actors.RockCritter(Point(x_0+i*16,140)))
        x_0 += 8*16
        globals.sounds.sw_bad_two.play()

        for i in xrange(10):
            self.critters.append(actors.RockCritter(Point(x_0+500+i*16,140)))

        self.tutorial_text.SetText("It's a world of laughter, a world of tears. It's a world of hope and a world of FEEAAARRRSS!")
        self.text_end = globals.time + 2000
        self.boat.move_direction = Point(0.2,0)
        for light in globals.lights:
            light.on = False
            self.timeofday.Set(0.0)
            self.flicker_start = globals.time
            self.flicker_end = globals.time + 4000

        for i in xrange(25):
            x = x_0 + random.random()*1000
            y = 120 + random.random()*120
            pos = Point(x,y)
            while any( ((pos - critter.pos).length() < 20) for critter in self.critters):
                #print 'skipping critter at',pos
                x = x_0 + random.random()*1000
                y = 120 + random.random()*120
                pos = Point(x,y)
            #print 'chose critter',pos
            self.critters.append(actors.Critter(pos))
        self.level_end = x_0 + 1000
        self.next_level = self.level_three

    def level_three(self):
        #same as one, but with a couple of arrow guys
        self.tutorial_text.SetText("It's a small world after all, It's a small world after all...")
        self.text_end = globals.time + 2000
        self.boat.move_direction = Point(0.3,0)
        globals.sounds.sw_bad_three.play()
        for light in globals.lights:
            light.on = False
            self.timeofday.Set(0.0)
            self.flicker_start = globals.time
            self.flicker_end = globals.time + 4000

        x_0 = self.viewpos.pos.x + globals.screen_showing.x
        self.critters.append(actors.BowCritter(Point(x_0, 140)))
        self.critters.append(actors.BowCritter(Point(x_0 + 500, 180)))
        for i in xrange(25):
            x = x_0 + random.random()*1000
            y = 120 + random.random()*120
            pos = Point(x,y)
            while any( ((pos - critter.pos).length() < 20) for critter in self.critters):
                #print 'skipping critter at',pos
                x = x_0 + random.random()*1000
                y = 120 + random.random()*120
                pos = Point(x,y)
            #print 'chose critter',pos
            self.critters.append(actors.Critter(pos))
        self.level_end = x_0 + 1000
        self.next_level = self.level_four

    def level_four(self):
        #Last level is throw everything at the wall
        self.tutorial_text.SetText("Glllrrrg")
        self.text_end = globals.time + 2000
        self.boat.move_direction = Point(0.3,0)
        globals.sounds.sw_bad_four.play()
        for light in globals.lights:
            light.on = False
            self.timeofday.Set(0.0)
            self.flicker_start = globals.time
            self.flicker_end = globals.time + 4000

        x_0 = self.viewpos.pos.x + globals.screen_showing.x
        self.critters.append(actors.BowCritter(Point(x_0, 140)))
        self.critters.append(actors.BowCritter(Point(x_0 + 500, 180)))
        for i in xrange(25):
            x = x_0 + random.random()*1000
            y = 120 + random.random()*120
            pos = Point(x,y)
            while any( ((pos - critter.pos).length() < 20) for critter in self.critters):
                #print 'skipping critter at',pos
                x = x_0 + random.random()*1000
                y = 120 + random.random()*120
                pos = Point(x,y)
            #print 'chose critter',pos
            self.critters.append(actors.Critter(pos))
        self.level_end = x_0 + 1000
        self.next_level = self.level_five

    def level_five(self):

        x_0 = self.viewpos.pos.x + globals.screen_showing.x
        for i in xrange(10):
            self.critters.append(actors.RockCritter(Point(x_0+i*16,140)))
        x_0 += 8*16
        globals.sounds.sw_bad_five.play()

        for i in xrange(10):
            self.critters.append(actors.RockCritter(Point(x_0+500+i*16,140)))

        self.tutorial_text.SetText("It's a world of laughter, a world of tears. It's a world of hope and a world of FEEAAARRRSS!")
        self.text_end = globals.time + 2000
        self.boat.move_direction = Point(0.2,0)
        for light in globals.lights:
            light.on = False
            self.timeofday.Set(0.0)
            self.flicker_start = globals.time
            self.flicker_end = globals.time + 300000

        for i in xrange(30):
            x = x_0 + random.random()*1000
            y = 120 + random.random()*120
            pos = Point(x,y)
            while any( ((pos - critter.pos).length() < 20) for critter in self.critters):
                #print 'skipping critter at',pos
                x = x_0 + random.random()*1000
                y = 120 + random.random()*120
                pos = Point(x,y)
            #print 'chose critter',pos
            self.critters.append(actors.Critter(pos))
        self.level_end = x_0 + 1000
        self.next_level = self.win_game


    def win_game(self):
        print 'wg'
        self.StartMusic()
        self.game_over = True
        self.won = True
        self.game_over_frame.title.SetText('You win')
        self.game_over_frame.help.SetText('Press R to restart or any other key to exit')
        self.game_over_frame.Enable()
        self.game_over_start = globals.time

    def GameOver(self):
        globals.sounds.sw_bad_three.play()
        self.game_over = True
        #self.mode = modes.GameOver(self)
        self.game_over_frame.title.SetText('GAME OVER')
        self.game_over_frame.help.SetText('Press R to restart level or ESC to start over')
        self.game_over_start = globals.time
        self.game_over_frame.Enable()

    def KeyDown(self,key):
        self.mode.KeyDown(key)

    def KeyUp(self,key):
        if self.game_over:
            if self.won and key != pygame.K_r:
                #Just exit
                raise SystemExit('Come again')

            if not self.won and key == pygame.K_r:
                print 'restart level'
                h = self.level_start_health
                level = self.last_level
                self.reset()
                self.player.health = h
                level()

            elif (not self.won and key == pygame.K_ESCAPE) or self.won:
                print 'restart all'
                self.reset()
                self.level_one()
            else:
                return
            self.game_over_frame.Disable()
            self.game_over = False
            globals.pause_time += (globals.time - self.game_over_start)
            print 'pause_time',globals.pause_time
            self.tutorial = False
            self.player.damage(0)
            return

        if key == pygame.K_ESCAPE and self.tutorial:
            self.tutorial = False
            self.help_text.SetText(' ')
            self.last_level = self.next_level
            self.next_level()
        #if key == pygame.K_x:
        #    self.GameOver()
        #if key == pygame.K_DELETE:
        #    if self.music_playing:
        #        self.music_playing = False
        #        pygame.mixer.music.set_volume(0)
        #    else:
        #        self.music_playing = True
        #        pygame.mixer.music.set_volume(globals.music_volume)
        self.mode.KeyUp(key)

    def MouseMotion(self,pos,rel,handled):
        world_pos = self.viewpos.full_pos + pos
        self.mouse_pos = pos
        #print globals.mouse_world

        self.mode.MouseMotion(world_pos,rel)

        return super(GameView,self).MouseMotion(pos,rel,handled)

    def MouseButtonDown(self,pos,button):
        if button == 3:
            self.player.put_brolly_up()
        elif button == 1:
            self.player.prepare_brolly_swing()
        #else:
        #    self.player.damage(10)
        #    self.water.jiggle(globals.mouse_world.x, -10)

        if self.mode:
            pos = self.viewpos.full_pos + pos
            return self.mode.MouseButtonDown(pos,button)
        else:
            return False,False

    def MouseButtonUp(self,pos,button):
        if button == 3:
            self.player.put_brolly_down()
        elif button == 1:
            self.player.swing_brolly()
        if self.mode:
            pos = self.viewpos.full_pos + pos
            return self.mode.MouseButtonUp(pos,button)
        else:
            return False,False

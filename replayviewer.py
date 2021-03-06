#!/usr/bin/python3
from args import Args
from kwreplay import Player, KWReplay
from watcher import Watcher
from chunks import KWReplayWithCommands
from gnuplot import Gnuplot
from animation import TimelineViewer
from mapzip import MapZip
from filterquery import FilterQuery 
import io
import sys
import os
import time
import datetime
import subprocess
import wx
import analyzer
import webbrowser
import urllib.parse
import repair
import traceback
import tempfile
import utils
import imp



def calc_props( kwr ) :
	args = Args.args

	props = []
	props.append( kwr.map_name.lower() ) # map name
	props.append( kwr.desc.lower() ) # desc

	# wtf? why do we not get players?
	if not kwr.players :
		print( kwr.fname, "got problems with players" )
	else :
		for player in kwr.players :
			props.append( player.name.lower() )
			props.append( player.ip )
			aka = args.get_aka( player.ip )
			if aka :
				props.append( aka )
	
	# lowercase everything!
	for (i, prop) in enumerate( props ) :
		props[i] = prop.lower()

	return props



# Returns True on some condition hit.
# Used for filtering replays.
def filter_hit( filter, props ) :
	if not filter :
		# either filter == None or empty string!
		return True

	so = sys.stdout # intercept stdout temporarily.
	se = sys.stderr
	f = io.StringIO()
	sys.stdout = f
	sys.stderr = f

	try :
		return filter.match( props )
	except :
		if filter.postfix :
			print( filter.postfix )
		traceback.print_exc()

		msg = "Error in query!\n\n"
		msg += f.getvalue()
		msg += "\n"
		wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )

	return True



# Not just the replay class, this class is for ease of management in rep_list.
class ReplayItem() :
	def __init__( self ) :
		self.fname = None # without path!!! = not full path!
		self.kwr = None
		self.id = -1

class ReplayItems() :
	def __init__( self ) :
		self.items = []
		self.id = 0 # Keep available UID for newly appended replays.

	def append( self, it ) :
		self.items.append( it )
		it.id = self.id
		self.id += 1

	# delete the replay with fname from items
	def find( self, fname=None, id=None ) :
		assert fname != None or id != None
		assert not ( fname != None and id != None )

		if fname :
			return self.find_fname( fname )
		else :
			return self.find_id( id )

	# Since I'm only appending items (not not shuffling them)
	# I should be able to do a binary search... but, nah, not now.
	def find_id( self, id ) :
		for it in self.items :
			if it.id == id :
				return it
		raise KeyError
	
	def find_fname( self, fname ) :
		fname = os.path.basename( fname ) # incase...
		for it in self.items :
			if it.fname == fname :
				return it
		raise KeyError

	# Happens when u delete a repaly from replay view.
	def remove( self, fname ) :
		it = self.find( fname )
		self.items.remove( it )

	# rename it.fname
	def rename( self, src, dest ) :
		it = self.find( src ) # find does basename for me.
		dest = os.path.basename( dest )
		it.fname = dest

	# scan a folder and return the replays as ReplayItem.
	def scan_path( self, path ) :
		fs = []
		for f in os.listdir( path ) :
			if not os.path.isfile( os.path.join( path, f ) ) :
				continue

			# must be a C&C replay file.
			ext = os.path.splitext( f )[1]
			ext = ext.lower()
			if not ext in [ ".kwreplay", ".ra3replay", ".cnc3replay" ] :
				continue

			fs.append( f )

		self.items = []
		for f in fs :
			i = ReplayItem()
			i.fname = f
			full_name = os.path.join( path, f )
			try :
				i.kwr = KWReplay( fname=full_name )
				self.append( i )
			except :
				msg = full_name + " is an invalid replay!"
				wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )

	

class MapView( wx.StaticBitmap ) :
	# maps: mapzip file name
	# mcmap: map CRC mapping to discern which 1.02+ map it is.
	def __init__( self, parent, maps, mcmap, size=(200,200), pos=(0,0) ) :
		super().__init__( parent, size=size, pos=pos )

		# Like self.replay_items, load map images into memory and keep them
		# it doesn't load everything from the beginning. it is loaded on request in
		# set_map_preview().
		self.map_previews = {} # holder!
		self.mapzip = MapZip( maps )
		self.mcmap = mcmap

	# ui: statisbitmap to fit in.
	# img: img that will go into ui.
	def calc_best_wh( self, img ) :
		(w, h) = self.GetSize()
		(x, y) = img.GetSize()

		# lets try fitting ...
		#x1 = w # x/x*w
		y1 = int( y*w/x )

		x2 = int( x*h/y )
		#y2 = h # y/y*h

		if y1 < h and x2 < x :
			# if both sizes fit, go for larger area.
			area1 = w*y1
			area2 = x2*h
			if area1 > area2 :
				return (w, y1)
			else :
				return (x2, h)
		elif y1 <= h :
			return (w, y1)
		elif x2 <= w :
			return (x2, h)
		else :
			assert 0 # one of them should fit!!

	def draw_102( self, img, mc ) :
		bmp = wx.Bitmap( img )
		dc = wx.MemoryDC( bitmap=bmp )

		sz = 30
		txt = "1.02+"
		if mc in self.mcmap :
			txt += self.mcmap[ mc ]
		else :
			txt += "MC=" + mc
			sz = 20

		# Set text props
		dc.SetTextForeground( wx.Colour( 255, 0, 255 ) )
		font = wx.Font( sz, wx.FONTFAMILY_SWISS,
			wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD )
		dc.SetFont( font )

		(tw, th) = dc.GetTextExtent( txt )
		# but our text is 15 deg rotated.
		# we need to compute 15deg rotation!
		# oh, I was being too smart. don't need to these.
		#(tw, th) = ( tw/1.414, tw/1.424 + th/1.414 )

		# draw text, centered.
		(w, h) = dc.GetSize()
		dc.DrawRotatedText( txt, int((w-tw)/2), int((h+th)/2), 15 )
		#dc.DrawText( txt, int((w-tw)/2), int((h-th)/2) )

		img = bmp.ConvertToImage()
		del dc
		return img

	# mc: mc of the replay to draw
	def set_map_preview( self, fname, mc, scale=True, watermark=True ) :
		# clear the image area first.
		# w, h may change. we generate it on every map change for sure.
		# Well, I can do that on size change but can't be bothered to do that...
		(w, h) = self.GetSize()
		black = wx.Image( w, h, clear=True )
		self.SetBitmap( wx.Bitmap( black ) )
		if not fname :
			return

		# We append mc to fname so that
		# when we draw 1.02+Rx, we draw again for different ver.
		if mc+fname in self.map_previews :
			# use previously loaded image
			img = self.map_previews[ mc+fname ]
		else :
			# now we show proper image.
			# I get "iCCP: known incorrect sRGB profile" for some PNG files.
			# Lets silence this with log null object.
			no_log = wx.LogNull()
			img = self.mapzip.load( fname )
			del no_log # restore

			# if 1.02+, draw 1.02+ on the image
			if watermark and fname.find( "1.02+" ) >= 0 :
				img = self.draw_102( img, mc )

			self.map_previews[ mc+fname ] = img # keep it in memory

		if scale == True :
			(w, h) = self.calc_best_wh( img )
			resized = img.Scale( w, h)
			self.SetBitmap( wx.Bitmap( resized ) )
		else :
			self.SetBitmap( wx.Bitmap( img ) )
	
	# show map preview
	def show( self, kwr, scale=True, watermark=True ) :
		# Examine the replay, determine what map it is.
		#print( kwr.map_id ) always says fake map id, useless.
		#print( kwr.map_name ) depends on language, not good.
		fname = kwr.map_path # this is one is the best shot.
		fname = os.path.basename( fname )
		fname += ".png"
		#print( fname )

		# file doesn't exist...
		if not self.mapzip.hasfile( fname ) :
			# well, try jpg.
			fname = fname.replace( ".png", ".jpg" )

		# file really doesn't exist...
		if not self.mapzip.hasfile( fname ) :
			fname = None
			# copy the name to clipboard so we can actually insert item to DB!
			data = wx.TextDataObject( kwr.map_path )
			wx.TheClipboard.Open()
			wx.TheClipboard.SetData( data )
			wx.TheClipboard.Close()

		# Load it and show it on the interface.
		self.set_map_preview( fname, kwr.mc, scale=scale, watermark=watermark )



# "selected" iterator for listctrls!
class selected( object ) :
	def __init__( self, list_ctrl ) :
		self.index = -1
		self.list_ctrl = list_ctrl

	def __iter__( self ) :
		return self

	def __next__( self ) :
		return self.next()

	def next( self ) :
		self.index = self.list_ctrl.GetNextSelected( self.index )
		if self.index == -1 :
			raise StopIteration()
		else :
			return self.index



class PlayerList( wx.ListCtrl ) :

	def __init__( self, parent, frame=None ) :
		super().__init__( parent, size=(600,200),
				style=wx.LC_REPORT|wx.LC_SINGLE_SEL )

		# parent frame to invoke event processing from upper level
		self.frame = frame
		self.kwr = None # remember the related replay.

		self.InsertColumn( 0, 'Team' )
		self.InsertColumn( 1, 'Name' )
		self.InsertColumn( 2, 'Faction' )
		self.InsertColumn( 3, 'Color' )
		self.InsertColumn( 4, 'Avg. APM' )
		self.SetColumnWidth( 1, 400 )
		#self.SetMinSize( (600, 200) )

		self.event_bindings()



	def populate( self, kwr ) :
		self.kwr = kwr # remember the replated replay
		self.DeleteAllItems()

		# Check if we have any filter.
		fil = self.frame.filter_text.GetValue()
		fil = FilterQuery( fil )

		for pid, p in enumerate( kwr.players ) :
			# p is the Player class. You are quite free to do anything!
			if p.name == "post Commentator" :
				# don't need to see this guy
				continue

			index = self.GetItemCount()
			if p.team == 0 :
				team = "-"
			else :
				team = str( p.team )
			pos = self.InsertItem( index, team )

			name = Args.args.akaed_name( p )
			self.SetItem( pos, 1, name )
			self.SetItem( pos, 2, p.decode_faction() )
			self.SetItem( pos, 3, p.decode_color() )
			self.SetItemData( pos, pid ) # remember pid of this guy.

			# Lets see if this player is a hit.
			props = [ p.name.lower(), p.ip ]
			aka = Args.args.get_aka( p.ip )
			if aka :
				props.append( aka )
			if fil and len( fil.postfix ) > 0 and filter_hit( fil, props ) :
				self.SetItemBackgroundColour( pos, wx.YELLOW )

		self.populate_apm( kwr )
	


	# Look up APM in the pre-calculated cache first.
	# return None if not calculated yet.
	def lookup_apm( self, kwr ) :
		if not "apm" in self.frame.cache :
			self.frame.cache[ "apm" ] = dict()
		cache = self.frame.cache[ "apm" ]

		# I'll use timestamp as its replay's UID...
		# It will work, almost 100%.
		key = kwr.timestamp

		if key in cache :
			return cache[ key ]
		else :
			return None
	


	def calc_apms( self, kwr ) :
		# Check if replay is selected.
		# frame.get_selected_replay will not work since it requires
		# selection of only one replay.
		# For this one, focused one is enough.
		pos = self.frame.rep_list.GetFocusedItem()
		rep_name = self.frame.rep_list.GetItem( pos, 0 ).GetText()
		fname = os.path.join( self.frame.rep_list.path, rep_name )

		if not fname :
			# error message is shown by get_selected_replay.
			return None

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.APMAnalyzer( kwr_chunks )
		cmds_at_second = ana.group_commands_by_time()
		avg_apms = ana.calc_avg_apm( cmds_at_second )

		result = [ int(val) for val in avg_apms ]
		return result

	

	def cache_apms( self, kwr, apms ) :
		# by now, this should hold.
		assert "apm" in self.frame.cache
		cache = self.frame.cache[ "apm" ]
		key = kwr.timestamp
		cache[ key ] = apms



	def populate_apm( self, kwr ) :
		# Well, lets populate APM.
		cached_apms = self.lookup_apm( kwr )
		apms = cached_apms

		if apms and len( apms ) < self.GetItemCount() :
			# cache collison occured or something.
			# We let the below alg. to calculate the APM.
			apms = None

		if not apms :
			if not Args.args.get_bool( 'calc_apm', default=False ) :
				cnt = self.GetItemCount()
				for pos in range( cnt ) :
					self.SetItem( pos, 4, "Enable APM analysis option in options menu!" )
				return

			try :
				apms = self.calc_apms( kwr )
			except :
				msg = "APM analysis failed!"
				wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )

		# successful lookup or calculation.
		# poopuate the list for real!
		if apms :
			cnt = self.GetItemCount()
			for pos in range( cnt ) :
				faction = self.GetItem( pos, 2 ).GetText()
				if faction in [ "Obs", "PostCommentator" ] :
					self.SetItem( pos, 4, "-" )
				elif apms[ pos ] == 0 :
					self.SetItem( pos, 4, "-" )
				else :
					self.SetItem( pos, 4, str( apms[ pos ] ) )

		# not cached so calculated -> newly save it in the cache!
		if ( not cached_apms ) and apms :
			self.cache_apms( kwr, apms )
	


	def get_uid_of_selected( self ) :
		# retrieve name then pass them to frame to do the
		# rest of the job. ('cos player list knows not much)
		if self.GetSelectedItemCount() == 0 :
			return None

		pos = self.GetFocusedItem()
		pid = self.GetItemData( pos )

		# from the replay, find the player to retrieve uid (=ip)
		player = self.kwr.players[ pid ]
		if player.is_ai :
			msg = "This player is AI!"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return None

		return (player, player.ip)



	# find replays involving a player, by context menu.
	def find_player( self, event ) :
		result = self.get_uid_of_selected()
		if not result :
			return
		player, uid = result
		if uid :
			self.frame.find_player( player.name, uid ) # the frame will do the rest.
	


	def search_shatabrick( self, evt ) :
		result = self.get_uid_of_selected()
		if not result :
			return
		player, uid = result

		if uid :
			if player.game == "KW" :
				game1 = "kw"
				game2 = game1
			elif player.game == "CNC3" :
				game1 = "tw"
				game2 = game1
			elif player.game == "RA3" :
				game1 = "ra3"
				game2 = "ra"
			else :
				wx.MessageBox( msg, "Invalid game replay", wx.OK|wx.ICON_ERROR )

			nick_encoded = urllib.parse.quote( player.name )

			#http://www.shatabrick.com/cco/kw/index.php?g=kw&a=sp&name=masterleaf
			#http://www.shatabrick.com/cco/tw/index.php?g=tw&a=h&Searchnick=amanoob
			#http://www.shatabrick.com/cco/ra3/index.php?g=ra&a=sp&name=worstnoob

			url = "http://www.shatabrick.com/cco/" + game1
			url += "/index.php?g=" + game2
			url += "&a=sp&name=" + nick_encoded

			# launch browser!
			webbrowser.open( url )



	def edit_aka( self, event ) :
		args = Args.args
		result = self.get_uid_of_selected()
		if not result :
			return
		player, uid = result
		aka = args.get_aka( uid )

		# Show edit dialog.
		dlg = wx.TextEntryDialog( self, "This player is also known as..." )
		if aka :
			dlg.SetValue( aka )
		dlg.ShowModal()
		result = dlg.GetValue()
		dlg.Destroy()

		if aka and (not result) : # had aka and user input was "".
			msg = "Remove AKA for this player?"
			yn = wx.MessageBox( msg, "Remove AKA?",
					wx.ICON_QUESTION|wx.YES|wx.NO_DEFAULT|wx.NO )
			if yn == wx.YES :
				args.remove_aka( uid )
		else :
			args.set_aka( uid, result )



	# create context menu
	def on_item_righ_click( self, event ) :
		# right clickable on empty space. prevent that.
		if self.GetSelectedItemCount() == 0 :
			return

		menu = wx.Menu()

		# find this guy
		item = wx.MenuItem( menu, wx.ID_ANY, "&Find replays involving this player" )
		menu.Bind( wx.EVT_MENU, self.find_player, id=item.GetId() )
		menu.Append( item )

		# find this guy on shatabrick.com
		item = wx.MenuItem( menu, wx.ID_ANY, "&Search this player on shatabrick.com" )
		menu.Bind( wx.EVT_MENU, self.search_shatabrick, id=item.GetId() )
		menu.Append( item )

		# create/edit AKA for this player
		item = wx.MenuItem( menu, wx.ID_ANY, "Create/Edit &AKA for this player" )
		menu.Bind( wx.EVT_MENU, self.edit_aka, id=item.GetId() )
		menu.Append( item )

		self.PopupMenu( menu, event.GetPoint() )
		menu.Destroy() # prevent memory leak



	def event_bindings( self ) :
		self.Bind( wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_item_righ_click )



# I guess I don't have to inherit this,
# Python's dynamicness can handle this alright...
# having just one extra var of replay_item...
# Actually, this is done with SetItemData!!!
#class ReplayListItem( wx.ListItem ) :
#	def __init__( self ) :
#		super().__init( self )
#		self.replay_item = None

class ReplayList( wx.ListCtrl ) :
	def __init__( self, parent, frame ) :
		super().__init__( parent, size=(-1,200),
				style=wx.LC_REPORT|wx.LC_EDIT_LABELS )
		self.InsertColumn( 0, 'Name' )
		self.InsertColumn( 1, 'Map' )
		self.InsertColumn( 2, 'Description' )
		self.InsertColumn( 3, 'Time' )
		self.InsertColumn( 4, 'Date' )
		self.SetColumnWidth( 0, 400 )
		self.SetColumnWidth( 1, 180 )
		self.SetColumnWidth( 2, 200 )
		self.SetColumnWidth( 3, 100 )
		self.SetColumnWidth( 4, 100 )
		#self.SetMinSize( (600, 200) )

		self.event_bindings()

		self.frame = frame
		self.replay_items = None # This is shared with frame, beware!
		self.path = None
		self.replay_items = ReplayItems()

		# sort stuff.
		self.last_clicked_col = 0 # last clicked column number
		self.ascending = True # sort by ascending order?



	def event_bindings( self ) :
		self.Bind( wx.EVT_LIST_ITEM_SELECTED, self.on_Click )
		self.Bind( wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_RightClick )
		self.Bind( wx.EVT_LIST_END_LABEL_EDIT, self.on_end_label_edit )
		self.Bind( wx.EVT_LIST_BEGIN_LABEL_EDIT, self.on_begin_label_edit )
		self.Bind( wx.EVT_LIST_COL_CLICK, self.on_col_click )
		self.Bind( wx.EVT_KEY_DOWN, self.on_key_down )

		# on key down doesn't work, for enter keys. :( :(
		#self.Bind( wx.EVT_LIST_KEY_DOWN, self.on_key_down )



	def on_key_down( self, event ) :
		key_code = event.GetKeyCode()
		if key_code == ord( 'A' ) and event.ControlDown() :
			self.select_all()
		else :
			event.Skip()



	def select_all( self ) :
		for i in range( self.GetItemCount() ) :
			self.Select( i )



	def set_path( self, path ) :
		self.path = path
		self.replay_items.scan_path( path )
		self.populate( self.replay_items )
		self.names = None # scratch memory for replay renaming presets (for context menu)
		self.ctx_old_name = "" # lets have a space for the old replay name too.
			# this one is for remembering click/right clicked ones only.
			# i.e, context menus.
		self.custom_old_name = ""
			# this one, is for remembering the old fname for custom renames.



	# reps: repaly_items
	def populate( self, reps, filter=None ) :
		self.replay_items = reps

		# destroy all existing items
		self.DeleteAllItems()

		# now read freshly.
		for rep in reps.items :
			self.add_replay( rep, filter=filter )

		# after filtering, sort.
		self.sort()



	def add_replay( self, rep, filter=None ) :
		fname = rep.fname
		kwr = rep.kwr

		props = calc_props( kwr )
		props.append( fname.lower() ) # fname is a prop, too
		if filter_hit( filter, props ) :
			# we need map, name, game desc, time and date.
			# Fortunately, only time and date need computation.
			t = datetime.datetime.fromtimestamp( kwr.timestamp )
			time = t.strftime("%X")
			date = t.strftime("%x")

			index = self.GetItemCount()
			pos = self.InsertItem( index, fname ) # replay name
			self.SetItem( pos, 1, kwr.map_name ) # replay name
			self.SetItem( pos, 2, kwr.desc ) # desc
			self.SetItem( pos, 3, time ) # time
			self.SetItem( pos, 4, date ) # date
			self.SetItemData( pos, rep.id ) # associate replay



	# Modify the description of the replay which is currently selected.
	def modify_desc( self, desc ) :
		if self.GetSelectedItemCount() == 0 :
			# pressed modify! button without selecting anything.
			return

		# I think I could use self.ctx_old_name but...
		pos = self.GetFocusedItem()
		assert pos >= 0 # GetSelectedItemCount will assure it, but to be sure
		id = self.GetItemData( pos )

		rep = self.replay_items.find( id=id )
		fname = os.path.join( self.path, rep.fname )

		# so, old_name should be quite valid by now.
		kwr = KWReplay()
		kwr.modify_desc_inplace( fname, desc )

		# update it in the interface.
		self.SetItem( pos, 2, desc ) # desc
		kwr = KWReplay( fname ) # reload it.
		rep.kwr = kwr



	def get_related_replay( self, pos ) :
		rep_id = self.GetItemData( pos )
		rep_item = self.replay_items.find( id=rep_id )
		return rep_item



	def key_func( self, rep_id1, rep_id2 ) :
		col = self.last_clicked_col
		asc = self.ascending

		# Since API's sorting function will sort by what I have
		# SetItemData'ed, rep1 and rep2 are my replay items.
		rep1 = self.replay_items.find( id=rep_id1 )
		rep2 = self.replay_items.find( id=rep_id2 )
		#print( rep1.fname )
		#print( rep2.fname )

		if col == 0 :
			# name
			data1 = rep1.fname
			data2 = rep2.fname
		elif col == 1 :
			data1 = rep1.kwr.map_name
			data2 = rep2.kwr.map_name
		elif col == 2 :
			data1 = rep1.kwr.desc
			data2 = rep2.kwr.desc
		elif col == 3 :
			# time of the day...
			# I'll just use timestamp, who cares?
			data1 = rep1.kwr.timestamp
			data2 = rep2.kwr.timestamp
		elif col == 4 :
			# date
			data1 = rep1.kwr.timestamp
			data2 = rep2.kwr.timestamp
		else :
			print( "invalid col", col )
			assert 0

		if data1 == data2 :
			result = 0
		elif data1 < data2 :
			result = -1
		else :
			result = 1

		if not asc :
			result *= -1

		return result



	def sort( self ) :
		self.SortItems( self.key_func )



	# sort by clicked column
	def on_col_click( self, event ) :
		# determine ascending or descending.
		if self.last_clicked_col == event.GetColumn() :
			self.ascending = not self.ascending
		else :
			self.ascending = True
		self.last_clicked_col = event.GetColumn()

		# now lets do the sorting
		self.sort()



	def context_menu_rename( self, event ) :
		if not self.ctx_old_name :
			# pressed F2 without selecting any item!
			return
		item = self.GetFocusedItem()
		self.EditLabel( item )
	


	# scan commands in kwr, owner==pid.
	# If queue, placedown command is met, try to resolve the faction of the player
	# given by pid.
	def resolve_faction_with_commands( self, kwr, pid ) :
		for chunk in kwr.replay_body.chunks :
			for cmd in chunk.commands :
				chunk.decode_cmd( cmd )
				# use placedown'ed building to resolve faction.
				if cmd.player_id != pid :
					continue

				name = None
				if cmd.is_placedown() :
					if not cmd.building_type.startswith( "0x" ) :
						name = cmd.building_type
				elif cmd.is_queue() :
					if not cmd.unit_ty.startswith( "0x" ) :
						name = cmd.unit_ty

				if name :
					# Good thing I always prefixed faction name in front!
					data = name.split()
					faction = "Rnd_" + data[0]
					return faction

		return None



	# resolve random factions, if possible.
	# if not possible, just silently pass...
	def resolve_faction( self, kwr_fname ) :
		result = {}

		# Just try decoding. If it works, it is fine.
		# If it is not, pass.
		try :
			kwr = KWReplayWithCommands( fname=kwr_fname )

			for pid, p in enumerate( kwr.players ) :
				faction = p.decode_faction()
				if faction != "Rnd" :
					continue

				# scan commands
				faction = self.resolve_faction_with_commands( kwr, pid )
				if faction :
					# insert to map
					result[ p.name ] = faction
					args = Args.args
					aka = args.get_aka( p.ip )
					if aka :
						result[ aka ] = faction # insert aka, too, if any!

					continue # continue to the next player.

		except :
			# silently ignore chunk decoding.
			pass

		#print( result )
		return result



	# Resolve random faction, if possible.
	def context_menu_resolve_random( self, event ) :
		cnt = self.GetSelectedItemCount()
		if cnt == 0 :
			return

		for pos in selected( self ) :
			kwr = self.get_related_replay( pos ).kwr

			rep_name = self.GetItem( pos, 0 ).GetText()
			if rep_name.find( "(Rnd)" ) < 0 :
				#print( rep_name, "has no random in its name" )
				continue

			#print( rep_name, "has random" )

			# old full name
			old_name = rep_name
			old_name = os.path.join( self.path, old_name )

			# resolve factions
			factions = self.resolve_faction( old_name )
			if not factions :
				# no need to rename.
				continue

			#print( factions )
			old_stem = self.GetItem( pos, 0 ).GetText()
			new_stem = old_stem

			for pname, faction in factions.items() :
				pname = Watcher.sanitize_name( pname )
				src = pname + " (Rnd)"
				dest = pname + " (" + faction + ")"
				new_stem = new_stem.replace( src, dest )

			if old_stem == new_stem :
				diag = wx.MessageBox(
						"Unable to rename, probably because AKA information for some players is missing.",
						"Error", wx.OK|wx.ICON_ERROR )
			else :
				self.rename_with_stem( pos, old_name, new_stem )

		wx.MessageBox( "Done", "Info", wx.OK )



	# copy files to clipboard
	def context_menu_copy( self, event ) :
		args = Args.args

		first_copy = args.get_bool( "1st_copy", default=True )
		if first_copy :
			wx.MessageBox( "Copied to clipboard, paste it into any folder!" )
			called = args.set_var( "1st_copy", "false" )

		fnames = []
		for pos in selected( self ) :
			rep_name = self.GetItem( pos, 0 ).GetText()
			fname = os.path.join( self.path, rep_name )
			fnames.append( fname )

		# copy these into clipboard!
		data = wx.FileDataObject()
		for fname in fnames :
			data.AddFile( fname )
		wx.TheClipboard.Open()
		wx.TheClipboard.SetData( data )
		wx.TheClipboard.Close()



#	def context_menu_cut( self, event ) :
#		pass



	#def context_menu_paste( self, event ) :
	#	# paste, if file data.
	#	if wx.TheClipboard.Open() :
	#		if wx.TheClipboard.IsSupported( wx.DataFormat( wx.DF_FILENAME ) ) :
	#			data = wx.FileDataObject()
	#			wx.TheClipboard.GetData( data )
#
#				# paste these files!!
#				wx.CallLater( 10, self.OnDropFiles, 0, 0, data.GetFilenames() )
#
#			wx.TheClipboard.Close()


	# Delete this replay?
	def context_menu_delete( self, event ) :
		cnt = self.GetSelectedItemCount()
		if cnt == 0 :
			return

		pos = self.GetNextSelected( -1 ) # get first selected index
		rep_name = self.GetItem( pos, 0 ).GetText()

		# confirmation message
		msg = "Really delete " + rep_name
		if cnt == 1 :
			msg += "?"
		else :
			msg += " and " + str( cnt-1 ) + " others?"

		# ICON_QUESTION will not show up...  It is intended by the library.
		# Read http://wxpython.org/Phoenix/docs/html/MessageDialog.html for more info.
		result = wx.MessageBox( msg, "Confirm Deletion",
				wx.ICON_QUESTION|wx.OK|wx.OK_DEFAULT|wx.CANCEL )
		if result != wx.OK :
			return

		for pos in reversed( list( selected( self ) ) ) :
			rep_name = self.GetItem( pos, 0 ).GetText()
			fname = os.path.join( self.path, rep_name )

			self.DeleteItem( pos ) # delete from list
			self.replay_items.remove( rep_name ) # delete from mem
			os.remove( fname ) # delete the file
			self.ctx_old_name = None



	def open_containing_folder( self, event ) :
		# not relying wxPython!
		cmd = 'explorer /select,"%s"' % (self.ctx_old_name)
		#print( cmd )
		subprocess.Popen( cmd )



	# use cnc3reader.exe to repair the replay.
	def repair_replay( self, event ) :
		cnt = self.GetSelectedItemCount()
		pos = self.GetFocusedItem()
		if pos < 0 :
			return
		kwr = self.get_related_replay( pos ).kwr
		fname = self.ctx_old_name

		if kwr.game == "KW" :
			ext = "Kane's Wrath Replay (*.KWReplay)|*.KWReplay"
		elif kwr.game == "CNC3" :
			ext = "Tiberium Wars Replay (*.CNC3Replay)|*.CNC3Replay"
		elif kwr.game == "RA3" :
			ext = "Red Alert 3(*.RA3Replay)|*.RA3Replay"
		else :
			msg = "Unable to determine game type"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return

		# Get ofname
		diag = wx.FileDialog( self, "Repair Replay As...", "", "", ext,
			wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT )
		path, basename = os.path.split( fname )
		diag.SetDirectory( path )
		diag.SetFilename( "repaired_" + basename )
		
		if diag.ShowModal() != wx.ID_OK :
			return None

		ofname = diag.GetPath()
		diag.Destroy()

		tmp1 = sys.stdout # intercept stdout temporarily.
		tmp2 = sys.stderr # intercept stdout temporarily.
		f = io.StringIO()
		sys.stdout = f
		sys.stderr = f

		# repair the replay
		fixer = repair.KWReplayRepair()
		fixer.repair( fname, ofname, game=kwr.game )

		msg = f.getvalue()
		f.close()
		sys.stdout = tmp1
		sys.stderr = tmp2

		# Show output from the repair.
		wx.MessageBox( msg, "Repair Log", wx.OK )



	# Generate the context menu when rep_list is right clicked.
	def on_RightClick( self, event ) :
		cnt = self.GetSelectedItemCount()
		pos = event.GetIndex()
		if pos < 0 :
			return

		kwr = self.get_related_replay( pos ).kwr

		# get the replay file name
		# handled by "select" event: EVT_LIST_ITEM_SELECTED
		# ... I thought so but in fact, I can right click and rename multiple times without
		# generating EVT_LIST_ITEM_SELECTED.
		# Do it here again!
		rep_name = self.GetItem( pos, 0 ).GetText()
		fname = os.path.join( self.path, rep_name )
		self.ctx_old_name = fname
		ext = os.path.splitext( fname )[1]

		# generate some predefined replay renamings
		self.names = []
		# having only date seems silly but for people with custom date format, it may be useful.
		# I'm keeping it.
		self.names.append( Watcher.calc_name( kwr,
				add_username=False, add_faction=False, add_vs_info=False,
				custom_date_format=Args.args.custom_date_format, ext=ext ) )
		#self.names.append( Watcher.calc_name( kwr,
		#		add_username=False, add_faction=True, custom_date_format=Args.args.custom_date_format ) )
		# add_faction is meaningless without add_username, duh!
		self.names.append( Watcher.calc_name( kwr,
				add_username=True, add_faction=False, add_vs_info=False,
				custom_date_format=Args.args.custom_date_format, ext=ext ) )
		self.names.append( Watcher.calc_name( kwr,
				add_username=True, add_faction=True, add_vs_info=False,
				custom_date_format=Args.args.custom_date_format, ext=ext ) )
		self.names.append( Watcher.calc_name( kwr,
				add_username=True, add_faction=False, add_vs_info=True,
				custom_date_format=Args.args.custom_date_format, ext=ext ) )
		self.names.append( Watcher.calc_name( kwr,
				add_username=True, add_faction=True, add_vs_info=True,
				custom_date_format=Args.args.custom_date_format, ext=ext ) )

		# make context menu
		menu = wx.Menu()

		# delete replay menu
		item = wx.MenuItem( menu, -1, "&Delete (Del)" )
		menu.Bind( wx.EVT_MENU, self.context_menu_delete, id=item.GetId() )
		menu.Append( item )

		item = wx.MenuItem( menu, -1, "Copy (Ctrl+&c)" )
		menu.Bind( wx.EVT_MENU, self.context_menu_copy, id=item.GetId() )
		menu.Append( item )

		# I found copy cut paste is a mess...
		# You can modify da clipboard, but it is impossible to discern whether
		# it was cut or copy from the file browser.

		#item = wx.MenuItem( menu, -1, "Cut (Ctrl+&x)" )
		#menu.Bind( wx.EVT_MENU, self.context_menu_cut, id=item.GetId() )
		#menu.Append( item )

		#item = wx.MenuItem( menu, -1, "Paste (Ctrl+&v)" )
		#menu.Bind( wx.EVT_MENU, self.context_menu_paste, id=item.GetId() )
		#menu.Append( item )

		# Sep
		menu.AppendSeparator()

		# context menu using self.names :
		for i, txt in enumerate( self.names ) :
			# variable txt is a copy of the variable. I may modify it safely without
			# affecting self.names!
			txt = txt.replace( "&", "&&" ) # Gotcha, in wx.
			# & indicates a shortcut key. I must say && to actually display & in the menu.
			if cnt > 1 :
				prefix = "Rename like "
			else :
				prefix = "Rename as "
			item = wx.MenuItem( menu, i, prefix + txt )
			menu.Bind( wx.EVT_MENU, self.context_menu_presetClicked, id=item.GetId() )
			menu.Append( item )

		# custom rename menu
		if cnt == 1 :
			item = wx.MenuItem( menu, -1, "&Rename (F2)" )
			menu.Bind( wx.EVT_MENU, self.context_menu_rename, id=item.GetId() )
			menu.Append( item )

		# resolve random
		item = wx.MenuItem( menu, -1, "R&esolve Random" )
		menu.Bind( wx.EVT_MENU, self.context_menu_resolve_random, id=item.GetId() )
		menu.Append( item )

		# open contaning folder
		if cnt == 1 :
			menu.AppendSeparator()

			item = wx.MenuItem( menu, -1, "&Open containing folder" )
			menu.Bind( wx.EVT_MENU, self.open_containing_folder, id=item.GetId() )
			menu.Append( item )

			item = wx.MenuItem( menu, -1, "Repair replay" )
			menu.Bind( wx.EVT_MENU, self.repair_replay, id=item.GetId() )
			menu.Append( item )

			item = wx.MenuItem( menu, -1, "&Play" )
			menu.Bind( wx.EVT_MENU, self.play, id=item.GetId() )
			menu.Append( item )
		
		self.PopupMenu( menu, event.GetPoint() ) # popup the context menu.
		menu.Destroy() # prevents memory leaks haha
	
	def play( self, event ) :
		# Play this replay
		if self.GetSelectedItemCount() == 0 :
			return
		if self.GetSelectedItemCount() > 1 :
			# probably pressed Enter key or something
			msg = "Please select only one replay to play!"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return

		pos = self.GetFocusedItem()
		rep_name = self.GetItem( pos, 0 ).GetText()
		fname = os.path.join( self.path, rep_name )
		os.startfile( fname ) # launch default app with file

	# Given new rep_name
	# do renaming in the file system and
	# update the entry in the viewer.
	# pos = rep_list entry position to update
	def do_renaming( self, pos, old_name, rep_name ) :
		assert pos >= 0
		# rename in the file system.
		assert old_name
		# self.custom_old_name is already with full path.
		if not os.path.isfile( old_name ) :
			# for some reason the old one may not exist.
			# perhaps due to not refreshed list.
			msg = "Replay does not exists! Please rescan the folder!"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return

		fname = os.path.join( self.path, rep_name )
		os.rename( old_name, fname )

		# rename in the viewer
		self.SetItem( pos, 0, rep_name ) # replay name
		# rename in the replay_items
		self.replay_items.rename( old_name, fname )

	# given some user friendly name "rep_name" as stem,
	# canonicalize it.
	# pos = rep_list entry position to update
	def rename_with_stem( self, pos, old_name, rep_name ) :
		old_ext = os.path.splitext( old_name )[1]

		# Add extension if not exists
		if not rep_name.lower().endswith( old_ext.lower() ) :
			rep_name += old_ext

		# sanitize invalid char
		rep_name = Watcher.sanitize_name( rep_name )

		# this is the full name.
		fname = os.path.join( self.path, rep_name )

		# see if it already exits.
		if os.path.isfile( fname ) :
			diag = wx.MessageBox( fname + "\nalready exists! Not renaming.", "Error",
					wx.OK|wx.ICON_ERROR )
		else :
			# rename the file
			self.do_renaming( pos, old_name, rep_name )

	def context_menu_presetClicked( self, event ) :
		assert self.names
		cnt = self.GetSelectedItemCount()
		index = event.GetId() # menu index

		if cnt == 1 :
			pos = self.GetFocusedItem()
			# Keeping self.names, for reading less from the disk.
			# I do think that it will be a neater code to remove this cnt==1 special case
			# but for the sake of performance, I'm keeping it.
			rep_name = self.names[ index ]
			self.rename_with_stem( pos, self.ctx_old_name, rep_name )
			return

		#
		# mass renaming case!
		#

		# compute parameter for calc_name.
		if index == 0 :
			au = False # add user info
			af = False # add faction info
			av = False # add vs info
		elif index == 1 :
			au = True
			af = False
			av = False
		elif index == 2 :
			au = True
			af = True
			av = False
		elif index == 3 :
			au = True
			af = False
			av = True
		elif index == 4 :
			au = True
			af = True
			av = True
		else :
			assert index <= 2

		# iterate list.
		for index in selected( self ) :
			# old full name
			it = self.get_related_replay( index )
			old_name = it.fname
			old_name = os.path.join( self.path, old_name )

			ext = os.path.splitext( old_name )[1]

			rep_name = Watcher.calc_name( it.kwr, add_username=au, add_faction=af,
					add_vs_info=av,
					custom_date_format=Args.args.custom_date_format, ext=ext )

			self.rename_with_stem( index, old_name, rep_name )


	def on_Click( self, event ) :
		pos = event.GetIndex()
		if pos < 0 :
			return

		# get the selected item and fill desc_text for editing.
		txt = self.GetItem( pos, 2 ).GetText()
		self.frame.desc_text.SetValue( txt )

		# get related replay.
		it = self.get_related_replay( pos )

		# remember the old name (for other renaming routines)
		self.ctx_old_name = os.path.join( self.path, it.fname )

		# fill faction info
		self.frame.player_list.populate( it.kwr )

		# load map preview
		self.frame.map_view.show( it.kwr )
	
	def on_end_label_edit( self, event ) :
		event.Veto() # undos all edits from the user, for now.

		#pos = self.GetFocusedItem()
		#if pos < 0 :
		#	return

		#if pos != event.GetIndex() :
		#	# User invoked renaming but clicked on another replay
		#	# In this case, silently quit edit.
		#	return

		pos = event.GetIndex() # maybe this is a more correct
		old_stem = self.GetItem( pos, 0 ).GetText()
		# if valid, the edit is accepted and updated by some update function.

		old_ext = os.path.splitext( old_stem )[1]

		stem = event.GetText() # newly edited text
		if old_stem == stem :
			# user pressed esc or something
			return

		if not stem.lower().endswith( old_ext.lower() ) :
			stem += old_ext

		# Check for invalid char
		sanitized = Watcher.sanitize_name( stem )
		if sanitized != stem :
			msg = "File name must not contain the following:\n"
			msg += "<>:\"/\\|?*"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return

		# Accepted.
		self.rename_with_stem( pos, self.custom_old_name, stem )

	def on_begin_label_edit( self, event ) :
		pos = event.GetIndex() # maybe this is a more correct
		stem = self.GetItem( pos, 0 ).GetText()
		self.custom_old_name = os.path.join( self.path, stem )
		# remember the old name from custom renaming
	


class ReplayViewer( wx.Frame ) :
	def __init__( self, parent ) :
		super().__init__( parent, title='Replay Info Viewer', size=(1024,800) )

		self.temp_files = [] # temp files...
		# temp files is required by "view commands" currently.
		# gnuplot has its own list to save temp files.
		# These files will be unlinked by on_close().

		path = os.path.dirname( Args.args.last_replay )

		self.is_min = False # on close, discern if this is actually a minimization action.
		# used by on_min

		self.MAPS_ZIP = 'maps.zip' # the name of the zip file that has map previews
		self.do_layout()
		self.event_bindings()
		self.create_accel_tab()
		self.set_icon()

		self.make_menu()

		self.load_win_props() # load win sz, win pos, ...

		self.rep_list.set_path( path )

		# don't need DB. we just set the image name right.
		#self.map_db = self.load_map_db( 'MapDB.txt' )

		# Save some calculated stuff in here, for acceleration.
		self.cachef = 'cache.py'
		self.cache = self.load_cache( self.cachef )
	


	def load_cache( self, fname ) :
		if os.path.isfile( fname ) :
			cache = imp.load_source( 'cache', fname )
			return cache.cache
		else :
			# if not exists, init a dictionary.
			return dict()



	def save_cache( self, fname ) :
		f = open( fname, "w" )
		print( "#!/usr/bin/python3", file=f )
		print( "cache = ", file=f, end="" )
		print( self.cache, file=f )
		f.close()
	


	def load_win_props( self ) :
		args = Args.args
		prefix = ""

		# maximized
		maxed = args.get_bool( "man_maximized", default=False )
		if maxed :
			prefix = "maxed_"

		# window sz
		w = args.get_int( "man_width", default=1024 )
		h = args.get_int( "man_height", default=800 )
		self.SetSize( (w, h) )

		# window pos
		x = args.get_int( "man_x", default=-1 )
		y = args.get_int( "man_y", default=-1 )
		if x >= 0 and y >= 0 :
			self.SetPosition( (x, y) )

		# sash pos
		sash_pos = args.get_int( prefix + "man_sash_pos", default=-1 )
		if sash_pos >= 0 :
			self.splitter.SetSashPosition( sash_pos )

		# actually do maximization.
		if maxed :
			self.Maximize()

		# load col width
		for i in range( self.rep_list.GetColumnCount() ) :
			w = args.get_int( prefix + "man_colw" + str( i ), default=-1 )
			if w >= 0 :
				 self.rep_list.SetColumnWidth( i, w )

		# sort criterions
		self.rep_list.last_clicked_col = args.get_int( "man_sort_by", default=0 )
		self.rep_list.ascending = args.get_bool( 'man_sort_ascending', default=True )



	def save_win_props( self ) :
		args = Args.args
		prefix = ""
		if self.IsMaximized() :
			prefix = "maxed_"
			args.set_var( "man_maximized", "true" )

		# window sz
		if not self.IsMaximized() :
			w, h = self.GetSize()
			args.set_var( "man_width", str( w ) )
			args.set_var( "man_height", str( h ) )

		# window pos
		if not self.IsMaximized() :
			x, y = self.GetPosition()
			args.set_var( "man_x", str( x ) )
			args.set_var( "man_y", str( y ) )

		# sash pos
		sash_pos = self.splitter.GetSashPosition()
		args.set_var( prefix + "man_sash_pos", str( sash_pos ) )

		# save col width
		for i in range( self.rep_list.GetColumnCount() ) :
			w = self.rep_list.GetColumnWidth( i )
			args.set_var( prefix + "man_colw" + str( i ), str( w ) )

		# save the option. How was it sorted?
		args.set_var( 'man_sort_by', str( self.rep_list.last_clicked_col ) )
		if self.rep_list.ascending :
			args.set_var( 'man_sort_ascending', 'true' )
		else :
			args.set_var( 'man_sort_ascending', 'false' )




	# Obsolete but, a working code. Keeping it in case I need it in future.
	def load_map_db( self, fname ) :
		f = open( fname )
		txt = f.read()
		f.close()
		#print( txt )
		# variable db is defined in txt!;;;;

		# looks funny that I can't use locals() as globals() in the parameter directly.
		# See this for details:
		# http://stackoverflow.com/questions/1463306/how-does-exec-work-with-locals
		ldict = locals()
		exec( txt, globals(), ldict )
		db = ldict[ 'db' ] # must pull it out from ldict explicitly!!;;;
		return db
	
	def change_dir( self ) :
		anyf = "Select_Any_File"
		diag = wx.FileDialog( None, "Select Folder", "", "",
			"Any File (*.*)|*.*",
			wx.FD_OPEN )
		diag.SetDirectory( self.rep_list.path )
		diag.SetFilename( anyf )
		
		if diag.ShowModal() == wx.ID_OK :
			path = os.path.dirname( diag.GetPath() )
			self.rep_list.set_path( path )

		diag.Destroy()

	# handles the request from PlayerList class and
	# tell filter object to find name and uid. (=ip)
	def find_player( self, name, uid ) :
		fil = name + " " + uid
		self.filter_text.SetValue( fil )
		self.rep_list.populate( self.rep_list.replay_items, filter=fil )
		
	def create_desc_panel( self, parent ) :
		desc_panel = wx.Panel( parent, -1 ) #, style=wx.SUNKEN_BORDER )
		game_desc = wx.StaticText( desc_panel, label="Game Description:", pos=(5,5) )
		self.desc_text = wx.TextCtrl( desc_panel, size=(400,-1),
				pos=(115,2), style=wx.TE_PROCESS_ENTER )
		self.modify_btn = wx.Button( desc_panel, label="Modify!", pos=(525,0) )
		return desc_panel
	
	def create_filter_panel( self, parent ) :
		filter_panel = wx.Panel( parent, -1 )
		filter_st = wx.StaticText( filter_panel, label="Filter", pos=(5,5) )
		self.filter_text = wx.TextCtrl( filter_panel, size=(400,-1),
				pos=(115,2), style=wx.TE_PROCESS_ENTER )
		self.apply_btn = wx.Button( filter_panel, label="Apply", pos=(525,0) )
		self.nofilter_btn = wx.Button( filter_panel, label="X",
				pos=(610,0), size=(50,wx.DefaultSize.y) )
		return filter_panel
	
	def create_ref_panel( self, parent ) :
		ref_panel = wx.Panel( parent, -1 ) #, style=wx.SUNKEN_BORDER )
		#panel.SetBackgroundColour("GREEN")
		self.opendir_btn = wx.Button( ref_panel, label="Change Folder", pos=(0,0) )
		self.refresh_btn = wx.Button( ref_panel, label="Rescan Folder", pos=(100,0) )
		return ref_panel

	def create_top_panel( self, parent ) :
		panel = wx.Panel( parent )

		self.player_list = PlayerList( panel, frame=self )
		self.map_view = MapView( panel, self.MAPS_ZIP, Args.args.mcmap, size=(200,200) )
		self.map_view.SetMinSize( (200, 200) )

		# sizer code
		sizer = wx.BoxSizer( wx.HORIZONTAL )
		sizer.Add( self.player_list, 1, wx.EXPAND)
		sizer.Add( self.map_view, 0, wx.ALIGN_CENTER )

		panel.SetSizer( sizer )
		panel.SetMinSize( (600, 200) )
		return panel

	def do_layout( self ) :
		self.SetMinSize( (900, 700) )
		main_sizer = wx.BoxSizer( wx.VERTICAL )
		self.splitter = wx.SplitterWindow( self ) # must go into a sizer :S
		self.splitter.SetMinimumPaneSize( 20 )
		main_sizer.Add( self.splitter, 1, wx.EXPAND )

		# top part of the splitter.
		# creates self.player_list, self.map_view
		top_panel = self.create_top_panel( self.splitter )

		#
		# bottom part of the splitter
		#
		# for splitter box resizing...
		bottom_panel = wx.Panel( self.splitter, size=(500,500) )

		self.rep_list = ReplayList( bottom_panel, self )

		# description editing
		# creates self.desc_text, self.modify_btn also.
		desc_panel = self.create_desc_panel( bottom_panel )

		# replay filtering
		# creates self.{filter_text, apply_btn, nofilter_btn} also.
		filter_panel = self.create_filter_panel( bottom_panel )

		# change folder and rescan folder buttons
		# creates self.{opendir_btn, refresh_btn}
		ref_panel = self.create_ref_panel( bottom_panel )

		# filter and ref panel are actually small enough to be merged
		# into a single bar.
		hbox1 = wx.BoxSizer( wx.HORIZONTAL )
		hbox1.Add( filter_panel, 1, wx.EXPAND )
		hbox1.Add( ref_panel, 0 )

		# tie bottom elements into a sizer.
		bottom_box = wx.BoxSizer( wx.VERTICAL )
		bottom_box.Add( hbox1, 0, wx.EXPAND)
		bottom_box.Add( desc_panel, 0, wx.EXPAND)
		bottom_box.Add( self.rep_list, 1, wx.EXPAND)
		bottom_panel.SetSizer( bottom_box )
		#bottom_box.SetMinSize( (600, 400 ) )

		self.splitter.SplitHorizontally( top_panel, bottom_panel )
		#self.splitter.SetSashGravity( 0.5 )

		self.SetAutoLayout(True)
		self.SetSizer( main_sizer )
		bottom_box.Fit( bottom_panel )
		self.Layout()

	def create_accel_tab( self ) :
		# Accelerator table (short cut keys)
		self.id_rename = wx.NewId()
		self.id_del = wx.NewId()
		self.id_copy = wx.NewId()

		self.Bind( wx.EVT_MENU, self.rep_list.context_menu_rename, id=self.id_rename )
		self.Bind( wx.EVT_MENU, self.rep_list.context_menu_delete, id=self.id_del )
		self.Bind( wx.EVT_MENU, self.rep_list.context_menu_copy, id=self.id_copy )

		accel_tab = wx.AcceleratorTable([
				( wx.ACCEL_NORMAL, wx.WXK_F2, self.id_rename ),
				( wx.ACCEL_NORMAL, wx.WXK_DELETE, self.id_del ),
				( wx.ACCEL_CTRL, ord('C'), self.id_copy ),
			])
		self.SetAcceleratorTable( accel_tab )
	
	def set_icon( self ) :
		icon = Args.args.icon
		if os.path.isfile( icon ) :
			icon = wx.Icon( icon, wx.BITMAP_TYPE_ICO )
			self.SetIcon( icon )

	def on_refresh_btnClick( self, event ) :
		self.filter_text.SetValue( "" ) # removes filter.
		self.rep_list.set_path( self.rep_list.path )

	# removing filter is the same as refresh_path but doesn't rescan path's files.
	def on_nofilter_btnClick( self, event ) :
		self.filter_text.SetValue( "" ) # removes filter.
		self.rep_list.populate( self.rep_list.replay_items )
	
	def on_opendir_btnClick( self, event ) :
		self.change_dir()
	

	def on_modify_btnClick( self, event ) :
		desc = self.desc_text.GetValue()
		self.rep_list.modify_desc( desc )
	
	def on_filter_applyClick( self, event ) :
		fil = self.filter_text.GetValue()
		fil = FilterQuery( fil )
		self.rep_list.populate( self.rep_list.replay_items, filter=fil )



	# For common use in analysis stuff...
	def get_selected_replay( self ) :
		if self.rep_list.GetSelectedItemCount() == 0 :
			msg = "No replay is selected for analysis."
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return None
		elif self.rep_list.GetSelectedItemCount() == 1 :
			pos = self.rep_list.GetFocusedItem()
			rep_name = self.rep_list.GetItem( pos, 0 ).GetText()
			fname = os.path.join( self.rep_list.path, rep_name )
			return fname
		else :
			msg = "Only one replay must be selected for analysis"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return None



	# For common use in analysis stuff...
	def save_as_csv_diag( self ) :
		diag = wx.FileDialog( self, "Save as CSV", "", "",
			"CSV File (*.csv)|*.csv",
			wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT )
		
		if diag.ShowModal() != wx.ID_OK :
			return None

		ofname = diag.GetPath()
		diag.Destroy()
		return ofname

	# For common use in analysis stuff...
	def save_as_txt_diag( self ) :
		diag = wx.FileDialog( self, "Save as Text", "", "",
			"TXT File (*.txt)|*.txt",
			wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT )
		
		if diag.ShowModal() != wx.ID_OK :
			return None

		ofname = diag.GetPath()
		diag.Destroy()
		return ofname



	def on_apm_csv( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return
		ofname = self.save_as_csv_diag()
		if not ofname :
			return
	
		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.APMAnalyzer( kwr_chunks )
		f = open( ofname, "w" )
		ana.emit_apm_csv( 10, file=f )
		f.close()



	def on_res_csv( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return
		ofname = self.save_as_csv_diag()
		if not ofname :
			return
	
		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.ResourceAnalyzer( kwr_chunks )
		ana.calc()
		f = open( ofname, "w" )
		ana.emit_csv( file=f )
		f.close()



	def gnuplot_ok( self ) :
		gp = Gnuplot.find_gnuplot()
		if not gp :
			msg = "gnuplot is not installed. Open gnuplot homepage?"
			result = wx.MessageBox( msg, "Error",
					wx.ICON_QUESTION|wx.YES|wx.YES_DEFAULT|wx.NO )
			if result == wx.YES :
				msg = "The recommended choice of download is gp466-win32-setup.exe."
				wx.MessageBox( msg, "Which version?", wx.OK )
				webbrowser.open( "http://www.gnuplot.info/" )
			return False
		else :
			return True
	


	def on_plot_apm( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		if not self.gnuplot_ok() :
			return

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.APMAnalyzer( kwr_chunks )
		ana.plot( 10 )



	def on_plot_res( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		if not self.gnuplot_ok() :
			return

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.ResourceAnalyzer( kwr_chunks )
		ana.calc()
		ana.plot()



	def on_plot_unit_dist( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		if not self.gnuplot_ok() :
			return

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.ResourceAnalyzer( kwr_chunks )
		ana.calc()
		ana.plot_unit_distribution()



	def on_build_order( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		ofname = self.save_as_txt_diag()
		if not ofname :
			return

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		tmp = sys.stdout # intercept stdout temporarily.
		f = open( ofname, "w" )
		sys.stdout = f
		kwr_chunks.replay_body.print_bo()
		f.close()
		sys.stdout = tmp



	def on_dump_cmds( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		ofname = self.save_as_txt_diag()
		if not ofname :
			return

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		tmp = sys.stdout # intercept stdout temporarily.
		f = open( ofname, "w" )
		sys.stdout = f
		kwr_chunks.replay_body.dump_commands()
		f.close()
		sys.stdout = tmp



	def on_view_cmds( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		of = tempfile.NamedTemporaryFile( mode="w", suffix=".txt", delete=False )
		assert of
		self.temp_files.append( of.name ) # remember this one, for deletion.

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		tmp = sys.stdout # intercept stdout temporarily.
		sys.stdout = of
		kwr_chunks.replay_body.dump_commands()
		of.close()
		sys.stdout = tmp

		utils.open_in_default_app( of.name )



	def on_dump_dist( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		ofname = self.save_as_txt_diag()
		if not ofname :
			return

		kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
		ana = analyzer.ResourceAnalyzer( kwr_chunks )
		ana.calc()

		tmp = sys.stdout # intercept stdout temporarily.
		f = open( ofname, "w" )
		sys.stdout = f
		ana.print_unit_distribution()
		f.close()
		sys.stdout = tmp
	


	def on_timeline( self, evt ) :
		# Check if replay is selected.
		fname = self.get_selected_replay()
		if not fname :
			# error message is shown by get_selected_replay.
			return

		so = sys.stdout # intercept stdout temporarily.
		se = sys.stderr
		f = io.StringIO()
		sys.stdout = f
		sys.stderr = f

		try :
			kwr_chunks = KWReplayWithCommands( fname=fname, verbose=False )
			tlv = TimelineViewer( self, maps_zip=self.MAPS_ZIP )
			tlv.load( kwr_chunks )
			tlv.Show()
		except :
			traceback.print_exc()

			msg = "An error occured. Please send this replay file to the auther!\n\n"
			msg += f.getvalue()
			msg += "\n"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )

		sys.stderr = se
		sys.stdout = so
		f.close()
	


	def on_exit( self, evt ) :
		self.Close() # generate close event.



	def on_min( self, evt ) :
		args = Args.args
		if args.get_bool( 'min_to_tray', default=False ) :
			self.is_min = True
			self.Close()
		else :
			evt.Skip()



	def on_close( self, evt ) :
		self.save_win_props()

		# remove gnuplot temp files
		for fname in Gnuplot.temp_files :
			os.unlink( fname )
		Gnuplot.temp_files = [] # purge the list.

		for fname in self.temp_files :
			os.unlink( fname )
		self.temp_files = [] # purge the list.

		self.save_cache( self.cachef )

		par = self.Parent
		if par :
			args = Args.args

			if self.is_min :
				# minimize to tray = self.Close().
				# In this case, don't kill tray actually.
				pass
			elif args.get_bool( 'close_to_tray', default=True ) == False :
				# if not close to tray, close the app.
				par.tray_icon.on_exit( evt )

		evt.Skip()
	


	def event_bindings( self ) :
		self.refresh_btn.Bind( wx.EVT_BUTTON, self.on_refresh_btnClick )

		self.modify_btn.Bind( wx.EVT_BUTTON, self.on_modify_btnClick )
		self.desc_text.Bind( wx.EVT_TEXT_ENTER, self.on_modify_btnClick )

		self.opendir_btn.Bind( wx.EVT_BUTTON, self.on_opendir_btnClick )

		self.apply_btn.Bind( wx.EVT_BUTTON, self.on_filter_applyClick )
		self.nofilter_btn.Bind( wx.EVT_BUTTON, self.on_nofilter_btnClick )
		self.filter_text.Bind( wx.EVT_TEXT_ENTER, self.on_filter_applyClick )

		self.Bind( wx.EVT_CLOSE, self.on_close ) # on close...
		self.Bind( wx.EVT_ICONIZE, self.on_min ) # on minimize...



	def make_dump_menu( self ) :
		dump_menu = wx.Menu()

		# dump build order
		build_order_menu_item = dump_menu.Append( wx.NewId(), "Dump &Build Order",
				"Dump build order to file" )
		dump_menu.Bind( wx.EVT_MENU, self.on_build_order, build_order_menu_item )

		# dump commands
		dump_cmds_menu_item = dump_menu.Append( wx.NewId(), "Dump &Commands",
				"Dump commands to file" )
		dump_menu.Bind( wx.EVT_MENU, self.on_dump_cmds, dump_cmds_menu_item )

		# APM to CSV
		apm_csv_menu_item = dump_menu.Append( wx.NewId(), "Dump &APM to CSV file",
				"Analyze the replay and calculate actions per minute of each player" )
		dump_menu.Bind( wx.EVT_MENU, self.on_apm_csv, apm_csv_menu_item )

		# Res to CSV
		res_csv_menu_item = dump_menu.Append( wx.NewId(), "Dump &Resource Spent to CSV file",
				"Analyze the replay and calculate resource spent of each player" )
		dump_menu.Bind( wx.EVT_MENU, self.on_res_csv, res_csv_menu_item )

		# dump unit distribution.
		dump_dist_menu_item = dump_menu.Append( wx.NewId(), "Dump &Unit Distribution",
				"Dump unit distribution to file" )
		dump_menu.Bind( wx.EVT_MENU, self.on_dump_dist, dump_dist_menu_item )

		return dump_menu



	def make_analysis_menu( self ) :
		analysis_menu = wx.Menu()

		# Plot APM
		plot_apm_menu_item = analysis_menu.Append( wx.NewId(), "Plot &APM",
				"Analyze the replay and calculate actions per minute of each player" )
		analysis_menu.Bind( wx.EVT_MENU, self.on_plot_apm, plot_apm_menu_item )

		# Plot Resource
		plot_res_menu_item = analysis_menu.Append( wx.NewId(), "Plot &Resource Spent",
				"Analyze the replay and calculate resource spent of each player" )
		analysis_menu.Bind( wx.EVT_MENU, self.on_plot_res, plot_res_menu_item )

		# draw time line
		timeline_menu_item = analysis_menu.Append( wx.NewId(), "Show &Timeline",
				"Show timeline along with movements on the minimap" )
		analysis_menu.Bind( wx.EVT_MENU, self.on_timeline, timeline_menu_item )

		# Plot unit distribution
		plot_unit_dist_menu_item = analysis_menu.Append( wx.NewId(), "Plot Estimated &Unit Distribution",
				"Plots estimated unit distribution" )
		analysis_menu.Bind( wx.EVT_MENU, self.on_plot_unit_dist, plot_unit_dist_menu_item )

		# View commands
		view_cmds_menu_item = analysis_menu.Append( wx.NewId(), "&View Commands",
				"Shows commands in the replay" )
		analysis_menu.Bind( wx.EVT_MENU, self.on_view_cmds, view_cmds_menu_item )

		# Sep.
		analysis_menu.AppendSeparator()

		exit_menu_item = analysis_menu.Append( wx.NewId(), "&Close",
				"Exits the program or this manager" )
		analysis_menu.Bind( wx.EVT_MENU, self.on_exit, exit_menu_item )

		return analysis_menu



	def on_close_to_tray( self, event ) :
		args = Args.args
		args.set_var( 'close_to_tray', 'true' )

	def on_close_the_app( self, event ) :
		args = Args.args
		args.set_var( 'close_to_tray', 'false' )

	def on_min_to_tray( self, event ) :
		args = Args.args
		args.set_var( 'min_to_tray', 'true' )

	def on_min_to_tbar( self, event ) :
		args = Args.args
		args.set_var( 'min_to_tray', 'false' )
	
	def on_calc_apm( self, event ) :
		args = Args.args
		if event.IsChecked() :
			val = 'true'
		else :
			val = 'false'
		args.set_var( 'calc_apm', val )



	def make_options_menu( self ) :
		options_menu = wx.Menu()

		# Plot APM
		on_close = wx.Menu()
		close_to_tray = on_close.Append( wx.ID_ANY, 'closes to tray', kind=wx.ITEM_RADIO )
		close_the_app = on_close.Append( wx.ID_ANY, 'closes the app', kind=wx.ITEM_RADIO )
		on_close.Bind( wx.EVT_MENU, self.on_close_to_tray, close_to_tray )
		on_close.Bind( wx.EVT_MENU, self.on_close_the_app, close_the_app )

		on_minimize = wx.Menu()
		min_to_tbar = on_minimize.Append( wx.ID_ANY, 'minimizes to taskbar', kind=wx.ITEM_RADIO )
		min_to_tray = on_minimize.Append( wx.ID_ANY, 'minimizes to tray', kind=wx.ITEM_RADIO )
		on_minimize.Bind( wx.EVT_MENU, self.on_min_to_tray, min_to_tray )
		on_minimize.Bind( wx.EVT_MENU, self.on_min_to_tbar, min_to_tbar )

		options_menu.Append( wx.ID_ANY, "Close...", on_close )
		options_menu.Append( wx.ID_ANY, "Minimize...", on_minimize )

		# calculate apm?
		calc_apm = options_menu.Append( wx.ID_ANY, 'Calculate APM', kind=wx.ITEM_CHECK )
		options_menu.Bind( wx.EVT_MENU, self.on_calc_apm, calc_apm )

		# read the val and apply it.
		args = Args.args
		if args.get_bool( 'close_to_tray', default=True ) :
			on_close.Check( close_to_tray.GetId(), True )
		else :
			on_close.Check( close_the_app.GetId(), True )

		if args.get_bool( 'min_to_tray', default=False ) :
			on_minimize.Check( min_to_tray.GetId(), True )
		else :
			on_minimize.Check( min_to_tbar.GetId(), True )

		# calc apm option
		checked = args.get_bool( 'calc_apm', default=False )
		options_menu.Check( calc_apm.GetId(), checked )

		return options_menu



	# This function is a very important one.
	# Many Args class variable are initialized here!
	# Those options not defined in args.py...
	# calc_apm, min_to_tray to name a few.
	def make_menu( self ) :
		menubar = wx.MenuBar()

		analysis_menu = self.make_analysis_menu()
		menubar.Append( analysis_menu, "&Analysis" )

		dump_menu = self.make_dump_menu()
		menubar.Append( dump_menu, "&Dump" )

		options_menu = self.make_options_menu()
		menubar.Append( options_menu, "&Options" )

		self.SetMenuBar( menubar )



def main() :
	app = wx.App()

	# debug settings
	CONFIGF = 'config.ini'
	args = Args( CONFIGF )

	frame = ReplayViewer( None )
	frame.Show( True )
	app.MainLoop()

	args.save()

if __name__ == "__main__" :
	main()

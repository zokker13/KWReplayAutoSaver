#!/usr/bin/python3
from args import Args
from kwreplay import Player, KWReplay
from watcher import Watcher
import os
import time
import datetime
import subprocess
import wx

KWICO='KW.ico'

class ReplayViewer( wx.Frame ) :
	def __init__( self, parent, args ) :
		super().__init__( parent, title='Replay Info Viewer', size=(1024,800) )
		self.do_layout()
		self.event_bindings()
		self.create_accel_tab()
		self.set_icon()

		self.args = args
		self.path = os.path.dirname( args.last_replay )
		self.populate_replay_list( self.path )

		self.names = None # scratch memory for replay renaming presets (for context menu)
		self.ctx_old_name = "" # lets have a space for the old replay name too.
			# this one is for remembering click/right clicked ones only.
			# i.e, context menus.
		self.custom_old_name = ""
			# this one, is for remembering the old fname for custom renames.

		# managing sort state XD
		self.last_clicked_col = -1 # last clicked column number
		self.ascending = True # sort by ascending order?
	
	def change_dir( self ) :
		anyf = "Select_Any_File"
		diag = wx.FileDialog( None, "Select Folder", "", "",
			"Any File (*.*)|*.*",
			wx.FD_OPEN )
		diag.SetFilename( anyf )
		
		if diag.ShowModal() == wx.ID_OK :
			self.path = os.path.dirname( diag.GetPath() )
			self.populate_replay_list( self.path ) # refresh list

		diag.Destroy()

	def scan_replay_files( self, path ) :
		fs = []
		for f in os.listdir( path ) :
			if not os.path.isfile( os.path.join( path, f ) ) :
				continue

			# must be a kwreplay file.
			if not f.lower().endswith( ".kwreplay" ) :
				continue

			fs.append( f )
		return fs

	# determine if filter hit -> show in rep_list.
	def filter_hit( self, filter, kwr, fname ) :
		if not filter :
			# either filter == None or empty string!
			return True

		# lower case everything
		fname = fname.lower()
		map_name = kwr.map_name.lower()
		words = filter.lower().split()
		players = []
		desc = kwr.desc.lower()
		for player in kwr.players :
			players.append( player.name.lower() )

		for word in words :
			# matches filename
			if word in fname :
				return True
			
			# matches map name
			if word in map_name :
				return True

			# matches description
			if word in desc :
				return True

			# matches player name
			for player in players :
				if word in player :
					return True

		return False

	def add_replay( self, path, rep, filter=None ) :
		fname = os.path.join( path, rep )
		kwr = KWReplay( fname=fname )

		if self.filter_hit( filter, kwr, fname ) :
			# we need map, name, game desc, time and date.
			# Fortunately, only time and date need computation.
			t = datetime.datetime.fromtimestamp( kwr.timestamp )
			time = t.strftime("%X")
			date = t.strftime("%x")

			index = self.rep_list.GetItemCount()
			pos = self.rep_list.InsertItem( index, rep ) # replay name
			self.rep_list.SetItem( pos, 1, kwr.map_name ) # replay name
			self.rep_list.SetItem( pos, 2, kwr.desc ) # desc
			self.rep_list.SetItem( pos, 3, time ) # time
			self.rep_list.SetItem( pos, 4, date ) # date
	
	def populate_replay_list( self, path, filter=None ) :
		# destroy all existing items
		self.rep_list.DeleteAllItems()

		# now read freshly.
		reps = self.scan_replay_files( path )
		for rep in reps :
			self.add_replay( path, rep, filter=filter )

	def populate_faction_info( self, pos ) :
		assert pos >= 0
		assert self.path
		self.player_list.DeleteAllItems()
		rep = self.rep_list.GetItem( pos, 0 ).GetText() # the replay fname
		fname = os.path.join( self.path, rep )
		kwr = KWReplay( fname=fname )

		for p in kwr.players :
			# p is the Player class. You are quite free to do anything!
			if p.name == "post Commentator" :
				# don't need to see this guy
				continue

			index = self.player_list.GetItemCount()
			if p.team == 0 :
				team = "-"
			else :
				team = str( p.team )
			pos = self.player_list.InsertItem( index, team )
			self.player_list.SetItem( pos, 1, p.name )
			self.player_list.SetItem( pos, 2, Player.decode_faction( p.faction ) )
			self.player_list.SetItem( pos, 3, Player.decode_color( p.color ) )

	# Generate the context menu when rep_list is right clicked.
	def replay_context_menu( self, event ) :
		cnt = self.rep_list.GetSelectedItemCount()
		pos = event.GetIndex()
		if pos < 0 :
			return

		# get the replay file name
		# handled by "select" event: EVT_LIST_ITEM_SELECTED
		# ... I thought so but in fact, I can right click and rename multiple times without
		# generating EVT_LIST_ITEM_SELECTED.
		# Do it here again!
		rep_name = self.rep_list.GetItem( pos, 0 ).GetText()
		fname = os.path.join( self.path, rep_name )
		self.ctx_old_name = fname

		# generate some predefined replay renamings
		kwr = KWReplay( fname=self.ctx_old_name )
		self.names = []
		# having only date seems silly but for people with custom date format, it may be useful.
		# I'm keeping it.
		self.names.append( Watcher.calc_name( kwr,
				add_username=False, add_faction=False, custom_date_format=self.args.custom_date_format ) )
		#self.names.append( Watcher.calc_name( kwr,
		#		add_username=False, add_faction=True, custom_date_format=self.args.custom_date_format ) )
		# add_faction is meaningless without add_username, duh!
		self.names.append( Watcher.calc_name( kwr,
				add_username=True, add_faction=False, custom_date_format=self.args.custom_date_format ) )
		self.names.append( Watcher.calc_name( kwr,
				add_username=True, add_faction=True, custom_date_format=self.args.custom_date_format ) )

		# make context menu
		menu = wx.Menu()
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
			menu.Bind( wx.EVT_MENU, self.replay_context_menu_presetClicked, id=item.GetId() )
			menu.Append( item )

		# custom rename menu
		if cnt == 1 :
			item = wx.MenuItem( menu, -1, "&Rename (F2)" )
			menu.Bind( wx.EVT_MENU, self.replay_context_menu_rename, id=item.GetId() )
			menu.Append( item )

		# delete replay menu
		item = wx.MenuItem( menu, -1, "&Delete (Del)" )
		menu.Bind( wx.EVT_MENU, self.replay_context_menu_delete, id=item.GetId() )
		menu.Append( item )

		# open contaning folder
		if cnt == 1 :
			item = wx.MenuItem( menu, -1, "&Open containing folder" )
			menu.Bind( wx.EVT_MENU, self.open_containing_folder, id=item.GetId() )
			menu.Append( item )
		
		self.rep_list.PopupMenu( menu, event.GetPoint() ) # popup the context menu.
		menu.Destroy() # prevents memory leaks haha
	
	def open_containing_folder( self, event ) :
		# not relying wxPython!
		cmd = 'explorer /select,"%s"' % (self.ctx_old_name)
		#print( cmd )
		subprocess.Popen( cmd )
	
	def replay_context_menu_rename( self, event ) :
		if not self.ctx_old_name :
			# pressed F2 without selecting any item!
			return
		item = self.rep_list.GetFocusedItem()
		self.rep_list.EditLabel( item )

	# Delete this replay?
	def replay_context_menu_delete( self, event ) :
		pos = self.rep_list.GetFocusedItem()
		if pos < 0 :
			return
		rep_name = self.rep_list.GetItem( pos, 0 ).GetText()

		# delete with DEL key, without focusing any item works but
		# at least, we have confirm
		# Glitch that I will not bother to fix.

		# ICON_QUESTION will not show up...  It is intended by the library.
		# Read http://wxpython.org/Phoenix/docs/html/MessageDialog.html for more info.
		result = wx.MessageBox( "Really delete " + rep_name + "?",
				"Confirm Deletion",
				wx.ICON_QUESTION|wx.OK|wx.OK_DEFAULT|wx.CANCEL )

		if result == wx.OK :
			# delete the file
			# the context menu should have old_name correct by now.
			assert self.ctx_old_name
			os.remove( self.ctx_old_name )
			# delete the list.
			self.rep_list.DeleteItem( pos )

	def replay_context_menu_presetClicked( self, event ) :
		assert self.names
		cnt = self.rep_list.GetSelectedItemCount()
		index = event.GetId() # menu index

		if cnt == 1 :
			pos = self.rep_list.GetFocusedItem()
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
			au = False
			af = False
		elif index == 1 :
			au = True
			af = False
		elif index == 2 :
			au = True
			af = True
		else :
			assert index <= 2

		# iterate list.
		index = -1
		while True :
			index = self.rep_list.GetNextSelected( index )
			if index == -1 :
				break

			# old full name
			old_name = self.rep_list.GetItem( index, 0 ).GetText()
			old_name = os.path.join( self.path, old_name )

			kwr = KWReplay( fname=old_name )

			rep_name = Watcher.calc_name( kwr, add_username=au, add_faction=af,
					custom_date_format=self.args.custom_date_format )

			self.rename_with_stem( index, old_name, rep_name )

	# given some user friendly name "rep_name" as stem,
	# canonicalize it.
	# pos = rep_list entry position to update
	def rename_with_stem( self, pos, old_name, rep_name ) :
		# Add extension if not exists
		if not rep_name.lower().endswith( ".kwreplay" ) :
			rep_name += ".KWReplay"

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
		self.rep_list.SetItem( pos, 0, rep_name ) # replay name
	
	def key_func( self, item, col ) :
		if col == 4 :
			# date!!!
			return time.strptime( item[ col ], "%x" )
		else :
			return item[ col ]
	
	def sort_rep_list( self, col, asc ) :
		items = self.retrieve_rep_list_items()
		items.sort( key=lambda item: self.key_func( item, col ) )
		if not asc :
			items.reverse()
		self.rep_list.DeleteAllItems()
		self.insert_rep_list_items( items )
	
	def insert_rep_list_items( self, items ) :
		for item in items :
			index = self.rep_list.GetItemCount()
			pos = self.rep_list.InsertItem( index, item[0] ) # replay name
			for i in range( 1, 5 ) :
				# other items
				self.rep_list.SetItem( pos, i, item[i] )

	def retrieve_rep_list_items( self ) :
		# turn all items into a list.
		items = []
		for i in range( self.rep_list.GetItemCount() ) :
			item = []
			for j in range( 5 ) : # there are 5 cols
				item.append( self.rep_list.GetItem( i, j ).GetText() )
			items.append( item )
		return items
	


	def create_player_list( self, parent ) :
		player_list = wx.ListCtrl( parent, size=(-1,200), style=wx.LC_REPORT )
		player_list.InsertColumn( 0, 'Team' )
		player_list.InsertColumn( 1, 'Name' )
		player_list.InsertColumn( 2, 'Faction' )
		player_list.InsertColumn( 3, 'Color' )
		player_list.SetColumnWidth( 1, 400 )
		player_list.SetMinSize( (600, 200) )
		return player_list
	
	def create_rep_list( self, parent ) :
		rep_list = wx.ListCtrl( parent, size=(-1,200),
				style=wx.LC_REPORT|wx.LC_EDIT_LABELS )
		rep_list.InsertColumn( 0, 'Name' )
		rep_list.InsertColumn( 1, 'Map' )
		rep_list.InsertColumn( 2, 'Description' )
		rep_list.InsertColumn( 3, 'Time' )
		rep_list.InsertColumn( 4, 'Date' )
		rep_list.SetColumnWidth( 0, 400 )
		rep_list.SetColumnWidth( 1, 180 )
		rep_list.SetColumnWidth( 2, 200 )
		rep_list.SetColumnWidth( 3, 100 )
		rep_list.SetColumnWidth( 4, 100 )
		#rep_list.SetMinSize( (600, 200) )
		return rep_list
	
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

	def do_layout( self ) :
		self.SetMinSize( (1024, 800) )
		main_sizer = wx.BoxSizer( wx.VERTICAL )
		splitter = wx.SplitterWindow( self ) # must go into a sizer :S
		splitter.SetMinimumPaneSize( 20 )
		main_sizer.Add( splitter, 1, wx.EXPAND )

		# top part of the splitter
		self.player_list = self.create_player_list( splitter ) # player list

		#
		# bottom part of the splitter
		#
		# for splitter box resizing...
		bottom_panel = wx.Panel( splitter, size=(500,500) )

		self.rep_list = self.create_rep_list( bottom_panel ) # replay list

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

		splitter.SplitHorizontally( self.player_list, bottom_panel )
		#splitter.SetSashGravity( 0.5 )

		self.SetAutoLayout(True)
		self.SetSizer( main_sizer )
		bottom_box.Fit( bottom_panel )
		self.Layout()

	def create_accel_tab( self ) :
		# Accelerator table (short cut keys)
		self.id_rename = wx.NewId()
		self.id_del = wx.NewId()

		self.Bind( wx.EVT_MENU, self.replay_context_menu_rename, id=self.id_rename )
		self.Bind( wx.EVT_MENU, self.replay_context_menu_delete, id=self.id_del )

		accel_tab = wx.AcceleratorTable([
				( wx.ACCEL_NORMAL, wx.WXK_F2, self.id_rename ),
				( wx.ACCEL_NORMAL, wx.WXK_DELETE, self.id_del )
			])
		self.SetAcceleratorTable( accel_tab )
	
	def set_icon( self ) :
		if os.path.isfile( KWICO ) :
			icon = wx.Icon( KWICO, wx.BITMAP_TYPE_ICO )
			self.SetIcon( icon )



	def on_refresh_btnClick( self, event ) :
		self.filter_text.SetValue( "" ) # removes filter.
		self.populate_replay_list( self.path )

	def on_opendir_btnClick( self, event ) :
		self.change_dir()
	
	def on_rep_listRightClick( self, event ) :
		self.replay_context_menu( event )

	def on_rep_listClick( self, event ) :
		pos = event.GetIndex()
		if pos < 0 :
			return
		# get the selected item and fill desc_text.
		txt = self.rep_list.GetItem( pos, 2 ).GetText()
		self.desc_text.SetValue( txt )

		# remember the old name
		rep = self.rep_list.GetItem( pos, 0 ).GetText()
		self.ctx_old_name = os.path.join( self.path, rep )

		# fill faction info
		self.populate_faction_info( pos )
	
	def on_rep_list_end_label_edit( self, event ) :
		event.Veto() # undos all edits from the user, for now.

		#pos = self.rep_list.GetFocusedItem()
		#if pos < 0 :
		#	return

		#if pos != event.GetIndex() :
		#	# User invoked renaming but clicked on another replay
		#	# In this case, silently quit edit.
		#	return

		pos = event.GetIndex() # maybe this is a more correct
		old_stem = self.rep_list.GetItem( pos, 0 ).GetText()
		# if valid, the edit is accepted and updated by some update function.

		stem = event.GetText() # newly edited text
		if old_stem == stem :
			# user pressed esc or something
			return

		if not stem.lower().endswith( ".kwreplay" ) :
			stem += ".KWReplay"

		# Check for invalid char
		sanitized = Watcher.sanitize_name( stem )
		if sanitized != stem :
			msg = "File name must not contain the following:\n"
			msg += "<>:\"/\\|?*"
			wx.MessageBox( msg, "Error", wx.OK|wx.ICON_ERROR )
			return

		# Accepted.
		self.rename_with_stem( pos, self.custom_old_name, stem )

	def on_rep_list_begin_label_edit( self, event ) :
		pos = event.GetIndex() # maybe this is a more correct
		stem = self.rep_list.GetItem( pos, 0 ).GetText()
		self.custom_old_name = os.path.join( self.path, stem )
		# remember the old name from custom renaming
	
	def on_modify_btnClick( self, event ) :
		if not self.ctx_old_name : 
			# pressed modify! button without selecting anything.
			return

		# I think I could use self.ctx_old_name but...
		pos = self.rep_list.GetFocusedItem()
		if pos < 0 :
			return
		rep = self.rep_list.GetItem( pos, 0 ).GetText()
		fname = os.path.join( self.path, rep )

		desc = self.desc_text.GetValue()

		# so, old_name should be quite valid by now.
		kwr = KWReplay()
		kwr.modify_desc_inplace( fname, desc )

		# update it in the interface.
		self.rep_list.SetItem( pos, 2, desc ) # desc

	# sort by clicked column
	def on_rep_list_col_click( self, event ) :
		# determine ascending or descending.
		if self.last_clicked_col == event.GetColumn() :
			self.ascending = not self.ascending
		else :
			self.ascending = True
		self.last_clicked_col = event.GetColumn()

		# now lets do the sorting
		self.sort_rep_list( event.GetColumn(), self.ascending )
	
	def on_filter_applyClick( self, event ) :
		fil = self.filter_text.GetValue()
		self.populate_replay_list( self.path, filter=fil )

	def event_bindings( self ) :
		self.refresh_btn.Bind( wx.EVT_BUTTON, self.on_refresh_btnClick )

		self.modify_btn.Bind( wx.EVT_BUTTON, self.on_modify_btnClick )
		self.desc_text.Bind( wx.EVT_TEXT_ENTER, self.on_modify_btnClick )

		self.opendir_btn.Bind( wx.EVT_BUTTON, self.on_opendir_btnClick )

		self.apply_btn.Bind( wx.EVT_BUTTON, self.on_filter_applyClick )
		self.nofilter_btn.Bind( wx.EVT_BUTTON, self.on_refresh_btnClick )
		self.filter_text.Bind( wx.EVT_TEXT_ENTER, self.on_filter_applyClick )

		self.rep_list.Bind( wx.EVT_LIST_ITEM_SELECTED, self.on_rep_listClick )
		self.rep_list.Bind( wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_rep_listRightClick )
		self.rep_list.Bind( wx.EVT_LIST_END_LABEL_EDIT, self.on_rep_list_end_label_edit )
		self.rep_list.Bind( wx.EVT_LIST_BEGIN_LABEL_EDIT, self.on_rep_list_begin_label_edit )
		self.rep_list.Bind( wx.EVT_LIST_COL_CLICK, self.on_rep_list_col_click )



def main() :
	app = wx.App()

	# debug settings
	CONFIGF = 'config.ini'
	args = Args( CONFIGF )

	frame = ReplayViewer( None, args )
	frame.Show( True )
	app.MainLoop()

if __name__ == "__main__" :
	main()

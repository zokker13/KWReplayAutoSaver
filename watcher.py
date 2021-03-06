#!/usr/bin/python3
# -*- coding: utf8 -*-
import os, time, shutil, datetime
from kwreplay import KWReplay, Player
from args import Args



class FileSignature :
	def __init__( self ) :
		self.ctime = 0
		self.mtime = 0
		self.size = 0
	
	def __str__( self ) :
		return str( self.ctime ) + " " + str( self.mtime) + " " + str( self.size )



class Watcher :
	def __init__( self, fname, verbose=False ) :
		self.verbose = verbose
		self.last_replay = fname
		self.sig = self.get_file_signature( fname )
		prefix, self.ext = os.path.splitext( fname )
	


	def get_file_signature( self, fname ) :
		if not os.path.isfile( fname ) :
			return None
		sig = FileSignature()
		sig.ctime = os.path.getctime( fname )
		sig.mtime = os.path.getmtime( fname )
		sig.size = os.path.getsize( fname )
		return sig

	# returns true when polled and replay has been modified.
	# false otherwise.
	def poll( self ) :
		# If not exists, then still fine.
		if not os.path.isfile( self.last_replay ) :
			return False

		new_sig = self.get_file_signature( self.last_replay )

		# replay is in writing process
		if self.is_writing( self.last_replay ) :
			return False

		if not new_sig :
			# non-existent or something.
			self.sig = None
			return False

		# empty replay
		if new_sig.size == 0 :
			return False
	
		if self.sig == None : # implicitly new_sig != None
			self.sig = new_sig
			return True
	
		# no change
		if self.sig.mtime == new_sig.mtime :
			return False

		self.sig = new_sig
		return True



	###
	### copy the last replay to a tmp replay
	### then use the replay's time stamp to give the tmp replay a proper name.
	### Setting add_username to True will append user name to the replay name.
	###
	### Decided to be independent form the Args class, that's why we have so many params here.
	###
	def do_renaming( self, fname, add_username=True,
			add_faction=False, add_vs_info=False,
			custom_date_format=None  ) :
		# where the replay dir is.
		path = os.path.dirname( fname )

		# Latch the replay file to a tmp file.
		# using folder where the replay is better
		tmpf = os.path.join( path, "tmp" + self.ext )
		shutil.copyfile( self.last_replay, tmpf )

		r = KWReplay( fname=tmpf )
		# analyze the replay and deduce its name
		newf = Watcher.calc_name( r, add_username=add_username,
				add_faction=add_faction, add_vs_info=add_vs_info,
				custom_date_format=custom_date_format, ext=self.ext )
		newf = os.path.join( path, newf )

		os.replace( tmpf, newf ) # rename, silently overwrite if needed.
		return newf

	def sanitize_name( newf ) :
		for char in [ "<", ">", ":", "\"", "/", "\\", "|", "?", "*" ] :
			newf = newf.replace( char, "_" )
		return newf

	# analyze the replay and deduce its name
	def calc_name( r, add_username=True,
			add_faction=False, add_vs_info=False,
			custom_date_format=None, ext=".kwr" ) :
		if custom_date_format == None :
			newf = '[' + r.decode_timestamp( r.timestamp ) + ']'
		else :
			# In this case, the user is responsible for adding [], if they want them.
			newf = r.decode_timestamp( r.timestamp, date_format=custom_date_format )

		if add_vs_info :
			vstag =  Watcher.vs_tag( r )
			if vstag : # could return None when no tag applicable!
				newf += " " + vstag

		if add_username :
			newf += " " + Watcher.player_list( r, add_faction=add_faction )

		#newf += ".KWReplay" # don't forget the extension!
		# more generalized RA3replay, cnc3replay extension is computed now.
		newf += ext # don't forget the extension!

		# sanitize the names.
		newf = Watcher.sanitize_name( newf )

		return newf

	# return [x vs y] or FFA.
	# The rest, we return None.
	def vs_tag( r ) :
		saver = Watcher.get_replay_saver( r )
		teams = Watcher.group_players_by_team( r ) # including AI, but no observers.
		teams = Watcher.saver_team_first( teams, saver )

		# neat x vs y case
		if len( teams ) == 2 :
			a = len( teams[0] )
			b = len( teams[1] )
			return "[%dv%d]" % (a, b)

		# check if FFA
		for t in teams :
			if len( t ) != 1 :
				return None
		return "[FFA]"

	# returns a nice readable list of players.
	# Actually only returns count and one player's name but anyway :S
	# r: da replay class instance.
	def player_list( r, add_faction=False ) :
		# count AI players.
		humans = Watcher.find_human_players( r )
		saver = Watcher.get_replay_saver( r )
		h = len( humans )
		ai = 0
		for p in r.players :
			if p.is_ai :
				ai += 1

		if h == 0 :
			# this can happen, when you observe and watch AIs fight each other, theoretically.
			return "AI only"
		elif h == 1 :
			if ai == 0 :
				return "Sandbox"
			else :
				return "vs AI"
		elif h+ai <= 4 :
			# why h+ai?
			# Otherwise I may get really long 8 player list, including the AI.

			# generate "ab vs cd" like style string
			# by now, h >= 2.

			teams = Watcher.group_players_by_team( r ) # including AI, but no observers.

			# * 'Sort' teams to have the saver player first.
			#   Well, the saver player could be an observer. should be careful of that.
			#     Hmm... if observer it doesn't matter too much. We just have to list
			#     the players in the game in that case, no sorting required.
			teams = Watcher.saver_team_first( teams, saver )

			# * Then, with the team with the player in, sort the players in the team
			#   so that the saver player come first.
			#   Even if the saver is an observer, it should be fine.
			teams[0] = Watcher.saver_first( teams[0], saver )

			# * Join the names in each team with " & ".
			team_strs = Watcher.teams_to_strs( teams, add_faction )

			# * Join teams with " vs ".
			return " vs ".join( team_strs )
		else :
			return str( h ) + "p game with " + \
				Watcher.player_to_str( Watcher.find_a_nonsaver_player( humans, saver ), add_faction )
	
	def player_to_str( p, add_faction ) :
		name = Args.args.aka_xor_name( p )
		if not add_faction :
			return name
		else :
			return name + " (" + p.decode_faction() + ")"
	
	def teams_to_strs( teams, add_faction ) :
		result = []
		for t in teams :
			names = [ Watcher.player_to_str( p, add_faction ) for p in t ]
			result.append( " & ".join( names ) )
		return result
	
	def saver_first( team, saver ) :
		if not saver in team :
			return team
		# if in team, move the saver to the first place.
		team.remove( saver )
		team.insert( 0, saver )
		return team

	# r: replay
	# Well, by players, that is AI included.
	# Ofcourse, observers are not players.
	def group_players_by_team( r ) :
		# prepare teams 0, 1, ..., 4
		teams = [ [] for i in range( 5 ) ]
		for p in r.players :
			# filter out non participants.
			# (obs, post commentators)
			if not p.is_player() :
				continue

			if p.team == 0 :
				teams.append( [p] ) # player is in no team!
			else :
				teams[ p.team ].append( p )

		# remove empty teams
		result = []
		for t in teams :
			if len( t ) > 0 :
				result.append( t )

		return result
	
	def saver_team_first( teams, saver ) :
		result = []
		for t in teams :
			# if saver is in the team, put the team as the first element of resul.
			if saver in t :
				result.insert( 0, t )
			else :
				result.append( t )
		return result

	# Find a player (that implies, not observer) who is not the replay saver.
	def find_a_nonsaver_player( humans, saver ) :
		for p in humans :
			if p != saver :
				return p



	# find all human "players".
	# If observer, they are not "playing" the game!, though they are human.
	# r: da replay class
	def find_human_players( r ) :
		ps = []
		for i, p in enumerate( r.players ) :
			if p.is_human_player() :
				ps.append( p )
		return ps

	def get_replay_saver( r ) :
		if r.replay_saver < 0 :
			return None
		if r.replay_saver >= len( r.players ) :
			return None
		# Well, epic_scorp.kwr in cornercases generates this error.
		# Replay saver is not a valid player! How on Earth did that happen?
		return r.players[ r.replay_saver ]

	###
	### Determine if the latest replay is occupied by the game.
	###
	def is_writing( self, fname ) :
		return not os.access( fname, os.W_OK )



def main() :
	#watcher = Watcher( "최종 리플레이.KWReplay", verbose=True )
	watcher = Watcher( "tw/last.CNC3Replay", verbose=True )
	# monitor file size change.
	print( watcher.sig )
	print( "Started monitoring" )

	while True :
		time.sleep (2)
		if watcher.poll() :
			newf = watcher.do_renaming( watcher.last_replay, add_username=True )
			print( watcher.sig )
			print( "Copied to", newf )



###
### main
###

if __name__ == "__main__" :
	main()

#!/usr/bin/python3
# coding: utf8

###
### http://www.gamereplays.org/community/index.php?showtopic=706067&st=0&p=7863248&#entry7863248
### The decoding of the replays format is credited to R Schneider.
###

import struct # bin file enc/dec
import sys
import re
import io
import codecs
import datetime
import time
from kwreplay import KWReplay, read_byte, read_uint32, time_code2str

CMDLENS = {
	0x01: -2,
	0x02: -2,
	0x03: -2,
	0x04: -2,
	0x05: -2,
	0x06: -2,
	0x07: -2,
	0x08: -2,
	0x09: -2,
	0x0B: -2,
	0x0C: -2,
	0x0D: -2,
	0x0F: -2,
	0x10: -2,
	0x11: -2,
	0x12: -2,
	0x17: -2,

	0x27: -34,
	0x29: 28,
	0x2B: -11,
	0x2C: 17,
	0x2E: 22,
	0x2F: 17,
	0x30: 17,
	0x34: 8,
	0x35: 12,
	0x36: 13,
	0x3C: 21,
	0x3E: 16,
	0x3D: 21,
	0x43: 12,
	0x44: 8,
	0x45: 21,
	0x46: 16,
	0x47: 16,
	0x48: 16,
	0x5B: 16,
	0x61: 20,
	0x72: -2,
	0x73: -2,
	0x77: 3,
	0x7A: 29,
	0x7E: 12,
	0x7F: 12,
	0x87: 8,
	0x89: 8,
	0x8C: 45,
	0x8D: 1049,
	0x8E: 16,
	0x8F: 40,
	0x90: 16,
	0x91: 10,

	0x28: 0,
	0x2D: 0,
	0x31: 0,
	0x8B: 0,
	0x8A: 0, # some unknown command, never seen before.

	0x26: -15,
	0x4C: -2,
	0x4D: -2,
	0x92: -2,
	0x93: -2,
	0xF5: -4,
	0xF6: -4,
	0xF8: -4,
	0xF9: -2,
	0xFA: -2,
	0xFB: -2,
	0xFC: -2,
	0xFD: -2,
	0xFE: -2,
	0xFF: -2
}

CMDNAMES = {
	0x2D: "not quit game... dunno",
	0x31: "Place down building",
	0x34: "sell?",
	0x3D: "attack?",
	0x61: "30s heartbeat",
	0x8F: "'scroll'",
	0xF5: "drag selection box and/or select units/structures",
	0xF8: "left click"
}

UNITNAMES = {
	0xA333C6A8: "Nod power plant",
	0x72407A4F: "Nod barracks",
	0xB5D275B6: "Nod refinery",
	0x22943F1D: "Nod factory",
	0x4E57EF4B: "Nod shredder turret",
	0xA46AA481: "Nod operations center",
	0xD5C63044: "Nod air tower",
	0x989B10EB: "Nod secret shrine",
	0xE630F233: "Nod tech center",
	0x8F61720F: "Nod tib chem plant",
	0x667CDE9C: "Nod crane",
	0xA78E52C1: "Nod redeemer eng. fac.",
	0xC04FB821: "Nod laser turret",
	0x821322AD: "Nod sam turret",
	0x5593CBD2: "Nod silo",
	0x9C462965: "Nod voice of Kane",
	0x0E4953BD: "Nod air support tower",
	0xE69ACCA8: "Nod obelisk of light",
	0x638C1170: "Nod temple of Nod",

	0x6BF191EB: "GDI crane",
	0x239262C6: "GDI power",
	0x13D568B3: "GDI barracks",
	0x16A86D68: "GDI ref",
	0xE1659649: "GDI command center",
	0x115E0E31: "GDI armory",
	0x9ABD65AC: "GDI factory",
	0x8314C7A0: "GDI airfield",
	0x33B40C6F: "GDI tech center",
	0x51474781: "GDI rec. hub",
	0x8136F6F6: "GDI space uplink",
	0x3EA580F4: "GDI watch tower",
	0x3554B096: "GDI guardian cannon",
	0xAD54632A: "GDI AA turret",
	0x15043F6B: "GDI silo",
	0xCD0835A6: "GDI sonic emitter",
	0x9D247A0D: "GDI support airfield",
	0xF1F5671A: "GDI ion cannon",

	0xE5F7D19B: "ST power plant",
	0x349BBD51: "ST barracks",
	0x6F3D0449: "ST watch tower",
	0x4C2E2C25: "ST ref",
	0x296BE097: "ST command center",
	0xA0426848: "ST crane",
	0xEEAC5E37: "ST airfield",
	0x40A17081: "ST factory",
	0x0F640F30: "ST space uplink",
	0xEABA4298: "ST rec. hub",
	0x6C309FAB: "ST tech center",
	0x358EB5E4: "ST guardian cannon",
	0x5C80259B: "ST AA turret",
	0x2C6EB27C: "ST silo",
	0xDF57BC42: "ST support airfield",
	0x01644BAB: "ST ion cannon",

	0x0A06D953: "BH crane",
	0x29BD08C8: "BH power plant",
	0x701FB486: "BH hand of nod",
	0x98F45D06: "BH shredder turrets",
	0x05F6FA50: "BH ref",
	0x2C62828E: "BH factory",
	0x23052F70: "BH operation center",
	0x0F62BDA5: "BH secret shrine",
	0x6F950650: "BH tech center",
	0x71F0EA3D: "BH redeemer eng. center",
	0x3232304B: "BH laser turrets",
	0xF5BD29E4: "BH SAM turrets",
	0xBCE723C7: "BH silo",
	0xCE205DD2: "BH tib. chem. plant",
	0xD78A3ED5: "BH voice of Kane",
	0xF2C0CB22: "BH obelisk of light",
	0x8D78D973: "BH temple of Nod",

	0x6753D4CA: "MoK crane",
	0xBDEA92DF: "MoK power plant",
	0x84B21B76: "MoK hand of nod",
	0x8161F095: "MoK shredder turrets",
	0x8ADF6801: "MoK secret shrine",
	0x40DCA116: "MoK ref.",
	0xE6D4B65C: "MoK factory",
	0xC6999B8E: "MoK operation center",
	0x8E42292A: "MoK air tower",
	0xF79AF4E3: "MoK tech center",
	0xF2A73707: "MoK Redeemer eng. fac.",
	0xD5326C9E: "MoK tib. chem. plant",
	0x3FC7B8E4: "MoK laser turrets",
	0x9D52F3D7: "MoK SAM turrets",
	0x17D5CAAA: "MoK silo",
	0x13517F79: "MoK voice of Kane",
	0x7CADE3A3: "MoK disruption tower",
	0x483EAEC0: "MoK obelisk of light",
	0xA12474B6: "MoK temple of Nod",
	0x75F7ECE5: "MoK support air tower",

	0x95A33CC6: "Sc power plant",
	0x0CA58AEF: "Sc ref.",
	0x929BD6C1: "Sc barracks",
	0xFEFD8CB5: "Sc factory",
	0xEEBC2492: "Sc nerve center",
	0x468981C5: "Sc gravity stabilizer",
	0xC1AFF92C: "Sc stasis chamber",
	0x951B67BA: "Sc tech center",
	0xE315D4B3: "Sc signal transmitter",
	0x550E8876: "Sc crane",
	0x23BE7BC2: "Sc warp chasm",
	0x0416A92F: "Sc buzzer hive",
	0xF4B32C4E: "Sc photon cannon",
	0xB6046563: "Sc plasma battery",
	0xDFCF8D47: "Sc growth accelerator",
	0x425D00A4: "Sc storm column",
	0x384EA3E7: "Sc rift generator",

	0x3CDBD279: "R17 power plant",
	0x7E291858: "R17 ref.",
	0x38A4A9E0: "R17 barracks",
	0x9A917351: "R17 factory",
	0xEFB4E2C0: "R17 nerve center",
	0x3A64AE56: "R17 gravity stabilizer",
	0xEB2D33E3: "R17 stasis chamber",
	0xDFDD1DA9: "R17 tech center",
	0x0C371C2A: "R17 signal transmitter",
	0x3400D06F: "R17 crane",
	0x589D2B2B: "R17 warp chasm",
	0x27C3413C: "R17 buzzer hive",
	0xBA9657C9: "R17 photon cannon",
	0x0FD56363: "R17 plasma battery",
	0xDBE925A9: "R17 growth accelerator",
	0x6862DB83: "R17 storm column",
	0xA503835E: "R17 rift generator",

	0x1F633A81: "T59 power plant",
	0xF4E73A51: "T59 ref.",
	0xAD3B9CCD: "T59 barracks",
	0x5743BC5C: "T59 factory",
	0x74F0DB70: "T59 nerve center",
	0x714AFABF: "T59 gravity stabilizer",
	0x73D55ACC: "T59 stasis chamber",
	0x9AF79C8D: "T59 tech center",
	0x3E28732D: "T59 signal transmitter",
	0xDE06E6CF: "T59 crane",
	0xA69624CC: "T59 warp chasm",
	0xD56430FB: "T59 buzzer hive",
	0x6AA8919A: "T59 photon cannon",
	0x385D26A8: "T59 plasma battery",
	0x730EA95B: "T59 growth accelerator",
	0x62697C2C: "T59 storm column",
	0x4379775A: "T59 rift generator",

	0xDCD2D288: "ZCM crane",
	0x34E71EC6: "ZCM power plant",
	0xBA62677D: "ZCM ref",
	0x502F0AAA: "ZCM watch tower",
	0x50EB58F7: "ZCM barracks",
	0xD2E0D294: "ZCM command center",
	0x8F222FF5: "ZCM factory",
	0xF2B92697: "ZCM airfield",
	0x7D372A88: "ZCM armory",
	0xD2CA793C: "ZCM silo",
	0x622F00EB: "ZCM guardian cannon",
	0xF689DAA0: "ZCM support airfield",
	0xE76FAF0F: "ZCM tech center",
	0x1F54F6C2: "ZCM space uplink",
	0xEBDE1709: "ZCM rec. hub",
	0xF459C486: "ZCM AA battery",
	0x089DA349: "ZCM sonic emitter",
}



def byte2int( byte ) :
	return struct.unpack( 'B', byte )[0]



def uint42int( bys ) :
	return struct.unpack( 'I', bys )[ 0 ]



class Chunk :
	def __init__( self ) :
		self.time_code = 0
		self.ty = 0
		self.size = 0
		self.data = None

		# decoded data
		self.time = 0
		self.paylaod = None

		# for ty == 1
		self.ncmd = 0

		# for ty == 2
		# player number, index in the player list in the plain-text game info
		self.player_number = 0
		self.time_code_payload = 0 # another timecode, in the paylaod.
		self.ty2_payload = None
	
	def decode_fixed_len( self, f, cmdlen ) :
		# that cmdlen includes the terminator and cmd code+0xff Thus, -3.
		cmdlen -= 3
		code = f.read( cmdlen )
		print( "fixed len, code:", code )
	
	def decode_var_len( self, f, cmdlen ) :
		cmdlen *= -1
		f.read( cmdlen-2 )
		print( "varlen:", cmdlen )
	
	def decode_placedown_cmd( self, ncmd, payload ) :
		building_type = uint42int( payload[ 8:12 ] )
		substructure_cnt = payload[ 12 ]
		print( "substructure_cnt:", substructure_cnt )
		print( "building_type: 0x%08X" % building_type, end="" )
		if building_type in UNITNAMES :
			print( ", " + UNITNAMES[ building_type ] )
		else :
			print()

		# For normal buildings, we don't get var length.
		# But for Nod defenses... shredder turrets, laser turrets,
		# SAM turrets... we get multiple coordinates.
		# That's why we get var len commands.
		# The multiplier 18 must be related to coordinates.
		# 8 for 2*4bytes (=2 floats) of x-y coords.
		# or... z coord?! dunno?!

		# old code...
		#unknown = f.read( 10 )
		#l = read_byte( f )
		#more_unknown = f.read( 18*l )
		#cmdlen = 3
		#more_unknown = f.read( 3 )

	
	def decode_commands( self, ncmd, payload ) :
		f = io.BytesIO( payload )
		print( "COMMANDS payload:", payload )

		for i in range( ncmd ) :
			cmd_id = read_byte( f )
			if cmd_id in CMDNAMES :
				print( "---" )
				print( CMDNAMES[ cmd_id ] )
				print( "---" )
			player_id = read_byte( f )
			print( "player_id:", player_id )
			print( "cmd_id: 0x%X" % cmd_id )
			# resolved the name.

			cmdlen = CMDLENS[ cmd_id ]

			if cmdlen < 0 :
				# var len cmds!
				self.decode_var_len( f, cmdlen )
				return

			# more var len commands
			if cmd_id == 0x31 :
				self.decode_placedown_cmd( ncmd, payload )
				return
			elif cmd_id == 0x2D :
				return
			elif cmd_id == 0x8A :
				# dunno if this is fixed or not even.
				return
			elif cmd_id == 0x28 :
				return
				#unknown = f.read( 5 )
				#some_code = read_byte( f )
				#if some_code == 0xFF :
				#	return # just, terminated.
				#else :
				#	buf = f.read( 17 )
				#	print( buf )
			else :
				# fixed len
				self.decode_fixed_len( f, cmdlen )

			terminator = read_byte( f )
			if terminator != 0xFF :
				print( "TERMINATOR:" )
				print( terminator )
				print( f.read() )
			assert terminator == 0xFF


	
	def decode( self ) :
		self.time = time_code2str( self.time_code/15 )
		if self.ty == 1 :
			f = io.BytesIO( self.data )
			one = read_byte( f )
			assert one == 1
			if self.data[ -1 ] != 0xFF :
				print( "Some unknown command format:" )
				print( "data:", self.data )
				self.payload = f.read()
			else :
				self.ncmd = read_uint32( f )
				self.payload = f.read()
				self.decode_commands( self.ncmd, self.payload )

		elif self.ty == 2 :
			f = io.BytesIO( self.data )
			# This is camera data or heart beat data.
			# I'll not try too hard to decode this.
			one = read_byte( f ) # should be ==1
			zero = read_byte( f ) # should be ==0
			self.player_number = read_uint32( f ) # uint32
			self.time_code_payload = read_uint32( f ) # time code...
			self.ty2_payload = f.read() # the payload
	
	def print( self ) :
		self.decode()

		if self.ty == 1 :
			print( "time:", self.time )
			print( "ncmd:", self.ncmd )
			print( "payload:" )
			for i in range( len( self.payload ) ) :
				print( "0x%02X" % self.payload[i], end=" " )
				if i % 16 == 0 :
					print()
			print()
			print()
			print()
		elif self.ty == 2 :
			#print( "Camera data." )
			pass
			#print( "\tplayer#:", self.player_number )
			#print( "\ttimecode:", self.time_code_payload )
		else :
			# From eareplay.html:
			# Chunk types 3 and 4 only appear to be present in replays with a
			# commentary track, and it seems that type 3 contains the audio
			# data and type 4 the telestrator data.
			pass
			#print( "type:", self.ty )
			#print( "size:", self.size )
			#print( "data:", self.data )
	


class ReplayBody :
	def __init__( self, f ) :
		self.chunks = []
		self.loadFromStream( f )
	
	def read_chunk( self, f ) :
		chunk = Chunk()
		chunk.time_code = read_uint32( f )
		#print( chunk.time_code )
		if chunk.time_code == 0x7FFFFFFF :
			return None

		chunk.ty = read_byte( f )
		chunk.size = read_uint32( f )
		chunk.data = f.read( chunk.size )
		zero = read_uint32( f )

		chunk.print()

		assert zero == 0
		return chunk
	
	def loadFromStream( self, f ) :
		while True :
			chunk = self.read_chunk( f )
			if chunk == None :
				break
			self.chunks.append( chunk )



class KWReplayWithCommands( KWReplay ) :
	def __init__( self, fname=None, verbose=False ) :
		self.replay_body = None

		# self.footer_str ... useless
		self.final_time_code = 0
		self.footer_data = None # I have no idea what this is. I'll keep it as it is.
		#self.footer_length = 0

		super().__init__( fname=fname, verbose=verbose )

	def read_footer( self, f ) :
		footer_str = self.read_cstr( f, self.FOOTER_MAGIC_SIZE )
		self.final_time_code = read_uint32( f )
		self.footer_data = f.read()
		if self.verbose :
			print( "footer_str:", footer_str )
			print( "final_time_code:", self.final_time_code )
			print( "footer_data:", self.footer_data )
			print()

	def loadFromFile( self, fname ) :
		f = open( fname, 'rb' )
		self.loadFromStream( f )
		self.replay_body = ReplayBody( f )
		self.read_footer( f )
		f.close()



###
###
###
def main() :
	fname = "1.KWReplay"
	if len( sys.argv ) >= 2 :
		fname = sys.argv[1]
	kw = KWReplayWithCommands( fname=fname, verbose=False )
	#kw = KWReplay()
	#kw.modify_desc( fname, "2.KWReplay", "매치 설명 있음" )
	#kw.modify_desc_inplace( "2.KWReplay", "show me the money 오예" )

if __name__ == "__main__" :
	main()

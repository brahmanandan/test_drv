#!/usr/bin/python
# -*- coding: utf-8 -*-

#####################################################################
# Doxygen Preprocessor - State Machine Handler                      #
# Author  : A. S. Budden                                            #
#####################################################################

# Core modules:
import os
import sys
import re
import optparse
import logging

# Local modules
from error_handler import ReportError
from doxycomment import ExtractCommentBlocks,\
		IsCommentBlockStart, IsCommentBlockEnd,\
		IsInCommentBlock, GetCommentBlock,\
		SplitLine, BlockHandler

# Currently this is hard-coded for tables with the @formatted tag.
# The intention is that this will be configurable.
ManualFormat = \
		{ \
			'FirstLine': \
			{ \
				'BackgroundColour': 'bgcolor="black"', \
				'Alignment':        'align="center"', \
				'Spanning':         'colspan="1"', \
				'Font':             'color="white"' \
			}, \
			'Table': \
			{ \
				'Border':           'border="0"', \
				'BackgroundColour': 'bgcolor="white"'
			}, \
			'Cells': \
			{ \
				'BackgroundColour': 'bgcolor="white"' \
			}
		}

def FormatRow(TableRow):
	Row = ""
	for cell in TableRow:
		CellString = "<td"
		if cell.has_key('BackgroundColour'):
			CellString += " " + cell['BackgroundColour']

		CellString += \
				cell['Alignment'] + \
				cell['CrossReference'] + \
				' id="' + cell['ID'] + '">'
		if cell.has_key('Font'):
			CellString += '<font ' + cell['Font'] + '>'
		CellString += cell['RowDetails']
		if cell.has_key('Font'):
			CellString += '</font>'
		CellString += '</td>'
		Row += CellString
	return Row

def ProcessTable(lineArray, TablePositions, CommentBlocks, options):
	# lineArray is the full array of file lines

	# TablePositions is a dictionary with 'Start' and 'End' being
	# the line indices into lineArray for the start and end of the comment
	# blocks containing @table and @endtable

	# CommentBlocks is details of where the comment blocks are
	TableHRRE = re.compile(r'^-+$')
	TableEntryRE = re.compile(r'^(\|.*\|)$')
	CrossRefRE = re.compile('^@ref\s+(?P<crossreference>\S+)\s+(?P<remainder>.*)')
	TableStartRE = re.compile(r'@table(?:\s+(?P<manual>@formatted))?')

	FoundTable = False
	TableLines = []
	TableParts = []
	DelayedLines = []
	TableRow = []
	IncludeFormatting = False

	for LineNumber in range(TablePositions['Start'], TablePositions['End']+1):
		ThisLine = lineArray[LineNumber]

		m = TableStartRE.search(ThisLine)
		if m is not None:
			index = m.start()
			if m.group('manual') is not None:
				IncludeFormatting = True
				Formatting = \
						ManualFormat['Table']['Border'] + " " + \
						ManualFormat['Table']['BackgroundColour'] + " "
			else:
				IncludeFormatting = False
				Formatting = ""

			TableParts = [ThisLine[:index] + '<table ' + Formatting + 'id="DoxyEmbeddedTable">']
			TableRow = []
			FoundTable = True
			continue

		if not FoundTable:
			TableLines.append(ThisLine)
			continue

		(Code, Comment) = SplitLine(ThisLine, LineNumber, CommentBlocks)

		if Comment is not None:
			Comment = Comment.strip()
			while Comment.startswith('*'):
				Comment = Comment[1:].strip()

			index = Comment.find('@endtable')
			if index != -1:
				FoundTable = False

				if len(TableRow) > 0:
					TableParts.append('<tr id="LastRow">' + FormatRow(TableRow) + "</tr>")
				TableParts.append("</table>" + Comment[index+len('@endtable'):])

				TableLines.append(" ".join(TableParts))
				TableParts = []

				if Code is None:
					DelayedLines.append("")
				else:
					DelayedLines.append(Code)

				TableLines += DelayedLines
				DelayedLines = []
				continue

			# If there's no code, just add a blank line
			if Code is None:
				DelayedLines.append("")

			if TableHRRE.match(Comment) is not None:
				if len(TableRow) >0:
					if IncludeFormatting:
						RowFormatting = \
								ManualFormat['FirstLine']['BackgroundColour'] + ' ' + \
								ManualFormat['FirstLine']['Alignment'] + ' ' + \
								ManualFormat['FirstLine']['Spanning']
						FontSelection = '<font ' + \
								ManualFormat['FirstLine']['Font'] + '>'
						EndFont = '</font>'

						for index in range(len(TableRow)):
							TableRow[index]['Font'] = ManualFormat['FirstLine']['Font']
							TableRow[index]['BackgroundColour'] = ManualFormat['FirstLine']['BackgroundColour']
					else:
						RowFormatting = ""
						FontSelection = ""
						EndFont = ""


					TableParts.append('<tr id="HeadRow" ' + \
							RowFormatting + '>' + \
							FormatRow(TableRow) + \
							"</tr>")
					TableRow = []
			elif TableEntryRE.match(Comment):
				m = TableEntryRE.match(Comment)
				TableRowString = m.group(1)
				if len(TableRow) > 0:
					TableParts.append('<tr id="BodyRow">' + FormatRow(TableRow) + "</tr>")
				ColumnNumber = 0
				TableRow = []
				if TableRowString.startswith('|'):
					TableRowString = TableRowString[1:]
				if TableRowString.endswith('|'):
					TableRowString = TableRowString[:-1]

				RowParts = TableRowString.split('|')

				for RowPart in RowParts:
					RowPart = RowPart.strip()
					Alignment = ""
					if RowPart.startswith('<'):
						RowPart = RowPart[1:].lstrip()
						Alignment = ' class="LeftAligned"'
					elif RowPart.startswith('>'):
						RowPart = RowPart[1:].lstrip()
						Alignment = ' class="RightAligned"'

					m = CrossRefRE.match(RowPart)
					if m is not None:
						CrossReference = r' href="\ref ' + m.group('crossreference') + '"'
						RowPart = m.group('remainder')
					else:
						CrossReference = ""

					ColumnNumber += 1

					if ColumnNumber == 1:
						ID = "FirstColumn"
					elif ColumnNumber == len(RowParts):
						ID = "LastColumn"
					else:
						ID = "MiddleColumn"

					ThisEntry = \
							{ \
								'Alignment': Alignment, \
								'CrossReference':  CrossReference, \
								'ID': ID, \
								'RowDetails': RowPart \
							}
					if IncludeFormatting:
						ThisEntry['BackgroundColour'] = ManualFormat['Cells']['BackgroundColour']
					TableRow.append(ThisEntry)

		if Code is not None:
			DelayedLines.append(Code)

	return TableLines


def EnhancedTableHandler(lineArray, options):

	return BlockHandler(lineArray, options,
			StartDelimiter='@table',
			EndDelimiter='@endtable',
			Processor=ProcessTable)

if __name__ == "__main__":
	# Parse command line
	from doxygen_preprocessor import CommandLineHandler
	options, remainder = CommandLineHandler()

	from filterprocessor import FilterFiles
	FilterFiles([EnhancedTableHandler,], options, remainder)

# vim:encoding=utf-8


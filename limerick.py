#!/usr/bin/env python
import argparse
import sys
import codecs
if sys.version_info[0] == 2:
  from itertools import izip
else:
  izip = zip
from collections import defaultdict as dd
import re
import os.path
import gzip
import tempfile
import shutil
import atexit
import itertools
import string

# Use word_tokenize to split raw text into words
from string import punctuation

import nltk
from nltk.tokenize import word_tokenize

scriptdir = os.path.dirname(os.path.abspath(__file__))

reader = codecs.getreader('utf8')
writer = codecs.getwriter('utf8')

def prepfile(fh, code):
  if type(fh) is str:
    fh = open(fh, code)
  ret = gzip.open(fh.name, code if code.endswith("t") else code+"t") if fh.name.endswith(".gz") else fh
  if sys.version_info[0] == 2:
    if code.startswith('r'):
      ret = reader(fh)
    elif code.startswith('w'):
      ret = writer(fh)
    else:
      sys.stderr.write("I didn't understand code "+code+"\n")
      sys.exit(1)
  return ret

def addonoffarg(parser, arg, dest=None, default=True, help="TODO"):
  ''' add the switches --arg and --no-arg that set parser.arg to true/false, respectively'''
  group = parser.add_mutually_exclusive_group()
  dest = arg if dest is None else dest
  group.add_argument('--%s' % arg, dest=dest, action='store_true', default=default, help=help)
  group.add_argument('--no-%s' % arg, dest=dest, action='store_false', default=default, help="See --%s" % arg)



class LimerickDetector:

    def __init__(self):
        """
        Initializes the object to have a pronunciation dictionary available
        """
        self._pronunciations = nltk.corpus.cmudict.dict()


    def num_syllables(self, word):
        """
        Returns the number of syllables in a word.  If there's more than one
        pronunciation, take the shorter one.  If there is no entry in the
        dictionary, return 1.
        """

        if word not in self._pronunciations:
            return 1
        else:
            pronuns = self._pronunciations[word]
        
            shortest_syllables = -1
        
            for this_pronun in pronuns:
                this_num_syllables = len([s for s in this_pronun if s[-1].isdigit()])
                if shortest_syllables == -1:
                    shortest_syllables = this_num_syllables
                elif this_num_syllables < shortest_syllables:
                    shortest_syllables = this_num_syllables

            return shortest_syllables

    def rhymes(self, a, b):
        """
        Returns True if two words (represented as lower-case strings) rhyme,
        False otherwise.
        """

        a_num_syllables = self.num_syllables(a)
        b_num_syllables = self.num_syllables(b)

        if a_num_syllables < b_num_syllables:
            shorter = a
            longer = b
        else:
            shorter = b
            longer = a

        if shorter not in self._pronunciations or longer not in self._pronunciations:
            return False
        else:
            shorter_pronuns = self._pronunciations[shorter]
            longer_pronuns = self._pronunciations[longer]

            for s_pronun in shorter_pronuns:
                shorter_sounds = s_pronun[[1 if s[-1].isdigit() else 0 for s in s_pronun].index(1):]
                last_n = 0-len(shorter_sounds)
                for l_pronun in longer_pronuns:
                    longer_sounds = l_pronun[[1 if s[-1].isdigit() else 0 for s in l_pronun].index(1):]
                    longer_sounds_last_n = longer_sounds[last_n:]
                    if shorter_sounds == longer_sounds_last_n:
                        return True


        return False

    def is_limerick(self, text):
        """
        Takes text where lines are separated by newline characters.  Returns
        True if the text is a limerick, False otherwise.

        A limerick is defined as a poem with the form AABBA, where the A lines
        rhyme with each other, the B lines rhyme with each other, and the A lines do not
        rhyme with the B lines.


        Additionally, the following syllable constraints should be observed:
          * No two A lines should differ in their number of syllables by more than two.
          * The B lines should differ in their number of syllables by no more than two.
          * Each of the B lines should have fewer syllables than each of the A lines.
          * No line should have fewer than 4 syllables

        (English professors may disagree with this definition, but that's what
        we're using here.)


        """
        
        lines = text.strip().split('\n')
        # There must be 5 lines in a limerick AABBA
        if len(lines) != 5:
            return False

        # contains number of syllables for corresponding line index
        num_sylls = []
        
        # contains the last word of each line
        last_word = []

        for line in lines:
            syllables = 0
            line_words = line.strip().split(" ")
            for line_word in line_words:
                syllables += self.num_syllables(line_word)
            # No line can have fewer than 4 syllables
            if num_sylls < 4:
                return False
            num_sylls.append(syllables)
            last_word.append(line_words[-1].translate(None, string.punctuation))

        A_lines_last_word = [last_word[0],last_word[1],last_word[4]]
        B_lines_last_word = [last_word[2],last_word[3]]
        
        A_syllables = [num_sylls[0],num_sylls[1],num_sylls[4]]
        B_syllables = [num_sylls[2],num_sylls[3]]

        # make sure A lines rhyme with each other
        if any(not self.rhymes(x.lower(),y.lower()) for x,y in itertools.combinations(A_lines_last_word,2)):
            return False

        # make sure B lines rhyme with each other
        if not self.rhymes(B_lines_last_word[0].lower(),B_lines_last_word[1].lower()):
            return False
        
        # make sure A lines don't rhyme with B lines
        if any(self.rhymes(x.lower(),y.lower()) for x,y in itertools.product(A_lines_last_word,B_lines_last_word)):
            return False
        
        # No two A lines should differ in their number of syllables by more than two
        if any(abs(x-y) > 2 for x,y in itertools.combinations(A_syllables,2)):
            return False
        
        # The B lines should differ in their number of syllables by no more than two
        if abs(B_syllables[0]-B_syllables[1]) > 2:
            return False
        
        # Each of the B lines should have fewer syllables than each of the A lines
        if any(x-y <= 0 for x,y in itertools.product(A_syllables,B_syllables)):
            return False
        
        return True


# The code below should not need to be modified
def main():
  parser = argparse.ArgumentParser(description="limerick detector. Given a file containing a poem, indicate whether that poem is a limerick or not",
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  addonoffarg(parser, 'debug', help="debug mode", default=False)
  parser.add_argument("--infile", "-i", nargs='?', type=argparse.FileType('r'), default=sys.stdin, help="input file")
  parser.add_argument("--outfile", "-o", nargs='?', type=argparse.FileType('w'), default=sys.stdout, help="output file")




  try:
    args = parser.parse_args()
  except IOError as msg:
    parser.error(str(msg))

  infile = prepfile(args.infile, 'r')
  outfile = prepfile(args.outfile, 'w')

  ld = LimerickDetector()
  lines = ''.join(infile.readlines())
  outfile.write("{}\n-----------\n{}\n".format(lines.strip(), ld.is_limerick(lines)))

if __name__ == '__main__':
#     ld = LimerickDetector()
#     e = """An exceedingly fat friend of mine,
# When asked at what hour he'd dine,
# Replied, "At eleven,     
# At three, five, and seven,
# And eight and a quarter past nine"""
#     print ld.is_limerick(e)
    main()

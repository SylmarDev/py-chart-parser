# Copyright (C) Sylvia Rothove - 2023

import pymupdf as pymupdf
import pyodbc
import re
import os
import itertools

# globals
date = ""
track = ""

paths = [] # strings of paths

# assign directory
directory = 'charts'

class Race():
    raceId = 0
    raceNo = 0
    fractionalTimes = ""
    finalTime = ""
    splitTimes = ""

    def __init__(self, rId, rN):
        self.raceId = rId
        self.raceNo = rN

    def toString(self):
        return f"Race {self.raceNo} (id:{self.raceId})\nFinal Time: {self.finalTime}"

    def toSqlInsert(self, raceId):
        return raceId, self.fractionalTimes, self.splitTimes, self.finalTime

# passed a list of race positions that need broken up
# needs to be up here because Horse class calls it iirc
# racePositions [currentPosition, lengthsAhead]
def parseRacePositions(li):
    racePositions = []
    for position in li:
        if len(position) == 1:
            racePositions.append([position, None])
            continue
        if "/" in position:
            pass
        # TODO: Cont from here


class Horse():
    raceNumber = 0
    position = 0
    isScratched = False

    lastRaced = ""
    pgm = ""
    name = ""
    pp = ""
    jockey = ""
    weight = ""
    me = ""
    racePositions = []
    odds = ""
    comments = ""

    def __init__(self, rN, p, isScratch):
        self.raceNumber = rN
        self.position = p
        self.isScratched = isScratch

    def toString(self):
        suffix = ""
        if self.position == 1:
            suffix = "st"
        elif self.position == 2:
            suffix = "nd"
        elif self.position == 3:
            suffix = "rd"
        else:
            suffix = "th"

        return f"{self.name}: {self.position}{suffix}"

    def updateFromChart(self, chartLi, racePositionCount, totalFinishers):
        self.lastRaced = chartLi[0].split(' ')[0]
        self.pgm = chartLi[1]
        self.name, self.jockey = parseNameAndJockey(chartLi[2])

        ppIndex = 0
        if isNumeric(chartLi[3]):
            self.weight = chartLi[3]
            self.me = chartLi[4].replace(" ", "")
            ppIndex = 5
        else:
            self.weight = "".join(itertools.takewhile(lambda x: isNumeric(x), chartLi[3]))
            self.me = chartLi[3][len(self.weight):].replace(" ", "")
            ppIndex = 4

        self.pp = chartLi[ppIndex]
        self.comments = chartLi[-1:][0]
        self.odds = chartLi[-2:-1][0]
        self.racePositions = chartLi[ppIndex+1:-2] # will need cleaned up a smidge before uploading

    def updateWithChartLine(self, chartLine, racePositionCount):
        self.racePositions = [[] * racePositionCount]

        # set last start date
        if startsWith(chartLine, "---"):
            self.lastRaced = "N/A" # first race
            chartLine = chartLine[4:]
        else:
            if isNumeric(chartLine[0]) and isNumeric(chartLine[1]):
                numberOfStartNumbers = 2
            elif isNumeric(chartLine[0]):
                numberOfStartNumbers = 1
            else:
                raise Exception("Invalid Date in chartLine")

            if isMonth(chartLine[numberOfStartNumbers : numberOfStartNumbers + 3]):
                self.lastRaced = chartLine[: numberOfStartNumbers + 5]
                chartLine = chartLine[numberOfStartNumbers + 5:]

        # PGM #
        self.pgm = extractPgmNumber(chartLine[:9])

        while (isNumeric(chartLine.split(' ')[0]) or chartLine.split(' ')[0] == " "):
            chartLine = chartLine.split(' ')

            # sometimes PGM not picked up
            if (self.pgm == "N/A" and isNumeric(chartLine[0])):
                self.pgm = chartLine[0]

            chartLine = " ".join(chartLine[1:])

        # Horse Name
        self.name = "".join(itertools.takewhile(lambda x: x != "(", chartLine))[:-1]

        # +2, one for space and one for (
        chartLine = chartLine[len(self.name) + 2:]

        # Jockey
        jName = "".join(itertools.takewhile(lambda x: x != ")", chartLine))
        jName = jName.split(",")
        self.jockey = f"{jName[1][1:]} {jName[0]}".replace("(", "") # in case it picks up a parathhenses

        # +3, one for space, one for comma, and one for )
        chartLine = chartLine[len(self.jockey) + 3:]

        # Weight
        self.weight = chartLine.split(" ")[0] if isNumeric(chartLine.split(" ")[0]) else "N/A"

        chartLine = chartLine.split(' ')
        chartLine = " ".join(chartLine[1:])

        # me
        chartLine = chartLine.split(' ')
        self.me = "".join(itertools.takewhile(lambda x: not isNumeric(x), chartLine))

        while (not isNumeric(chartLine[0])):
            chartLine = chartLine[1:]
        
        # pp
        self.pp = chartLine[0]

        # start
        self.racePositions[0] = [chartLine[1], None]
        
        chartLine = " ".join(chartLine[2:])

        additionalRaceFinishes, self.odds, self.comments = parseRacePositionsOddsAndComments(chartLine, racePositionCount-1) # -1 because start done above




        return


def parseNameAndJockey(text):
    jockeyNameIndex = text.rfind('(')

    # Split the string into two parts
    horseName = text[:jockeyNameIndex].strip()
    jockeyName = text[jockeyNameIndex:].strip()

    # Format Jockey Name
    nameDivisorIndex = jockeyName.rfind(',')
    jockeyName = f"{jockeyName[nameDivisorIndex:]} {jockeyName[:nameDivisorIndex]}"

    # Remove lingering parens and commas
    jockeyName = jockeyName.replace("(", "").replace(")", "").replace(",", "").strip()

    return horseName, jockeyName

def extractPgmNumber(text):
    # Define the regular expression pattern
    pattern = r'\b(\d+)(?=[A-Za-z]+\b)'
    
    # Search for matches in the input text
    match = re.search(pattern, text)
    
    if match:
        return int(match.group(1))
    else:
        return "N/A"

def parseRacePositionsOddsAndComments(input_string, finish_positions):
    comments = input_string.split(".")[1]
    spaces = 0
    while (isNumeric(comments[0]) or comments[0] == "*" or comments[0] == " "):
        if comments[0] == " ":
            spaces += 1
        comments = comments[1:]

    input_string = input_string[:-(len(comments)+spaces)]

    positions = []
    curPos = ""
    stopNext = False
    for char in input_string:
        curPos += char
        # head, nose, neck
        if stopNext or char is "d" or char is "e" or char is "k":
            positions.append(curPos)
            curPos = ""
            stopNext = False
            continue
        # 1/2 or 1/4 length
        if char is "/":
            stopNext = True

    # TODO: Cont from here

        
    
    # Extract the odds
    odds = re.search(r'\d+\.\d+\*?', input_string)
    odds = odds.group() if odds else None

    
    return racePositions, odds, comments

def extract_text_from_pdf(pdf_file: str) -> [str]:
        reader = pymupdf.open(pdf_file, filetype="pdf")
        # no_pages = len(reader.pages)
        pdf_text = []

        for page in reader:
            content = page.get_text("text")
            pdf_text.append(content)

        return pdf_text

 
def convertDateFormat(date_str):
    year = "20" + date_str[4:6]
    month = date_str[:2]
    day = date_str[2:4]
    return f"{year}-{month}-{day}"

def startsWith(string, prefix):
    i = 0
    if len(string) < len(prefix):
        return False

    while i < len(prefix):
        if (prefix[i] != string[i]):
            return False

        i += 1

    return True

def startsWithDate(string):
    numberOfStartNumbers = 0
    if len(string) < 2:
        return False

    # never started
    if startsWith(string, "---"):
        return True

    if isNumeric(string[0]) and isNumeric(string[1]):
        numberOfStartNumbers = 2
    elif isNumeric(string[0]):
        numberOfStartNumbers = 1
    else:
        return False

    if isMonth(string[numberOfStartNumbers : numberOfStartNumbers + 3]):
        return True

    return False

def isNumeric(char):
    try:
        int(char)
        return True
    except ValueError:
        return False

def isMonth(threeLetterString):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return threeLetterString in months

def getHorseNameFromChartString(chartString):
    i = 0
    goingBackwards = False
    stringStart = 0
    stringEnd = 0
    while i < len(chartString):
        if chartString[i] == '(':
            goingBackwards = True
            stringEnd = i - 1

        if goingBackwards and isNumeric(chartString[i]):
            stringStart = i + 1
            break

        if goingBackwards:
            i -= 1
        else:
            i += 1

    return chartString[stringStart:stringEnd].strip()

# return list
def getScratchedHorsesFromString(string):
    scratches = string.split(",") # return this
    return [scratch.split("(")[0].strip() for scratch in scratches]
    

# parse track and date from file name
def parseTrackAndDate(s):
    track = ""
    date = ""

    s = s.split('\\')[-1]

    for char in s:
        if char.isdigit():
            break
        track += char

    date = s[s.index(track) + len(track):].split('.')[0][:-3]

    return track, date

def getCallNo(lineLi, i):
    startIndex = 0
    findex = 0 # I'm so clever :)
    while i < len(lineLi):
        if startsWith(lineLi[i], "Start"):
            startIndex = i
        elif startsWith(lineLi[i], "Fin"):
            findex = i

        if startIndex != 0 and findex != 0:
            break
        i += 1

    # plus 1 for including finish
    return (findex - startIndex) + 1

def getSplitTimes(inputString):
    # pattern to match text within parentheses
    pattern = re.compile(r'\((.*?)\)')
    matches = pattern.findall(inputString)

    return matches


def __main__(path):
    print(f"Starting {track} // {date}")

    print("Reading PDF")
    extracted_text = extract_text_from_pdf(path)
    readInSwitch = False

    races = []
    horses = []
    scratchedHorses = []

    raceNo = 1
    placement = 1

    for text in extracted_text:
        # split_message = re.split(r'\s+|[,;?!.-]\s*', text.lower())
        #print(text)
        lines = text.split("\n")
        i = 0
        racePositionCount = 0

        if len(lines) > 1 and "Cancelled" in lines[1]:
            raceNo += 1
            continue
        
        while i < len(lines):
            if startsWith(lines[i], "Last Raced"):
                readInSwitch = True
                races.append(Race(raceNo, raceNo))

                #racePositionCount = getCallNo(lines, i) # get the number of calls in the race

                i += 1
                continue
            if readInSwitch:
                # do all the horse lines at once
                if startsWithDate(lines[i]):
                    allHorseLines = list(itertools.takewhile(lambda x: not startsWith(x, "Fractional"), lines[i:]))
                    # list of lists. each entry in this list is the list of values from the chart line
                    horseChartLines = []
                    for l in allHorseLines:
                        if startsWithDate(l):
                            horseChartLines.append([])
                        horseChartLines[len(horseChartLines)-1].append(l)

                    for l in horseChartLines:
                        horse = Horse(raceNo, placement, False)
                        horse.updateFromChart(l, racePositionCount, len(horseChartLines))
                        horses.append(horse)
                        placement += 1

                    # update i to where it belongs
                    i += len(allHorseLines)
                if startsWith(lines[i], "Fractional"):
                    fractionalTimesLi = list(itertools.takewhile(lambda x: not startsWith(x, "Final"), lines[i:]))
                    if startsWith(fractionalTimesLi[0], "Fractional"):
                        fractionalTimesLi[0] = fractionalTimesLi[0].replace("Fractional Times: ", "")
                    
                    races[len(races)-1].fractionalTimes = fractionalTimesLi

                    i += len(fractionalTimesLi)
                    races[len(races)-1].finalTime = lines[i].split("Final Time:")[1].strip()
                    i += 1
                if startsWith(lines[i], "Split"):
                    splitTimesLi = list(itertools.takewhile(lambda x: not startsWith(x, "Run"), lines[i:]))
                    races[len(races)-1].splitTimes = getSplitTimes(" ".join(splitTimesLi))
                    i += len(splitTimesLi)
                if startsWith(lines[i], "Scratch"):
                    allScratchString = lines[i]
                    ii = 1

                    # get all extra off the line
                    while not startsWith(lines[i + ii], "Total"):
                        allScratchString += lines[i + ii]
                        ii += 1

                    sh = getScratchedHorsesFromString(allScratchString.split(":")[1])
                    # horse in scratched Horses
                    for h in sh:
                        scratchedHorse = Horse(raceNo, "-1", True)
                        scratchedHorse.name = h
                        scratchedHorses.append(scratchedHorse)
            if startsWith(lines[i], "Total"):
                readInSwitch = False
                placement = 1
                raceNo += 1

            i += 1

    print("Read PDF successfully!")
    print(f"Preparing to load in {len(horses)} horses in {len(races)} races, as well as {len(scratchedHorses)} scratches to the database")

    print("Loading races into database...")
    print("stopping short")


    horsesAlreadyUpdatedNames = []

    for race in races:
        print(race.toString())

        for horse in horses:
            if horse.raceNumber == race.raceNo:
                print("\t" + horse.toString())

        anyScratches = False
        for horse in scratchedHorses:
            if horse.raceNumber == race.raceNo:
                if not anyScratches:
                    print("\nSCRATCHES:")
                    anyScratches = True
                print("\t" + horse.toString())

        print("\n")


    print("Finished")

for filename in os.listdir(directory):
    f = os.path.join(directory, filename)
    # checking if it is a file
    if os.path.isfile(f):
        paths.append(f)

for path in paths:
    track, date = parseTrackAndDate(path)
    __main__(path)
#!/usr/bin/python

from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser
import json

import requests

from pymongo import MongoClient
client = MongoClient()

db = client['scheduler']
collection = db['cachedData']

#define semester
SEMESTER = 'F17'

def convertTime(x):
	if(x[-2:] == "AM"):
		return x[:2] + x[-4:-2]
	else:
		if int(x[:2]) == 12:
			return x[:2] + x[-4:-2]
		else:
			return str(int(x[:2])+12) + x[-4:-2]

def getKeys(header):
    cookie = {}
    
    keySections = header['Set-Cookie'].split(", ")
    
    for x in keySections:
        cookie[x.split('=')[0]] = x.split('=')[1]
        
    return cookie

def getDescription(Code, Level):
    return collection.find_one({'Code': Code})

def findIndex(courseObject, toFind):
    for i,x in enumerate(courseObject):
        if x['Course']['Course'] == toFind:
            return i
    return -1

def getData(dataToSend):
    getURL = 'https://webadvisor.uoguelph.ca/WebAdvisor/WebAdvisor?CONSTITUENCY=WBST&type=P&pid=ST-WESTS12A&TOKENIDX='
    r = requests.get(getURL)
    cookie = getKeys(r.headers)
    
    getURL = 'https://webadvisor.uoguelph.ca/WebAdvisor/WebAdvisor?CONSTITUENCY=WBST&type=P&pid=ST-WESTS12A&TOKENIDX=' + cookie['LASTTOKEN']
    r = requests.get(getURL, cookies=cookie)
    
    try:
        cookie = getKeys(r.headers)
    except:
        return "Error: Webadvisor seems to be down"
    
    # 1 stores class
    # 3 stores course code
    
    postURL = 'https://webadvisor.uoguelph.ca/WebAdvisor/WebAdvisor?TOKENIDX=' + cookie['LASTTOKEN'] + '&SS=1&APP=ST&CONSTITUENCY=WBST'
    postfields = {"VAR1":SEMESTER, "VAR10":"Y", "VAR11":"Y","VAR12":"Y", "VAR13":"Y", "VAR14":"Y", "VAR15":"Y", "VAR16":"Y", "DATE.VAR1":"", "DATE.VAR2":"", "LIST.VAR1_CONTROLLER":"LIST.VAR1", "LIST.VAR1_MEMBERS":"LIST.VAR1*LIST.VAR2*LIST.VAR3*LIST.VAR4", "LIST.VAR1_MAX":"5", "LIST.VAR2_MAX":"5", "LIST.VAR3_MAX":"5", "LIST.VAR4_MAX":"5", "LIST.VAR1_1":dataToSend[0][0], "LIST.VAR2_1":"", "LIST.VAR3_1":dataToSend[0][1], "LIST.VAR4_1":"", "LIST.VAR1_2":dataToSend[1][0], "LIST.VAR2_2":"", "LIST.VAR3_2":dataToSend[1][1], "LIST.VAR4_2":"", "LIST.VAR1_3":dataToSend[2][0], "LIST.VAR2_3":"", "LIST.VAR3_3":dataToSend[2][1], "LIST.VAR4_3":"", "LIST.VAR1_4":dataToSend[3][0], "LIST.VAR2_4":"", "LIST.VAR3_4":dataToSend[3][1], "LIST.VAR4_4":"", "LIST.VAR1_5":dataToSend[4][0], "LIST.VAR2_5":"", "LIST.VAR3_5":dataToSend[4][1], "LIST.VAR4_5":"", "VAR7":"", "VAR8":"", "VAR3":"", "VAR6":"", "VAR21":"", "VAR9":"", "SUBMIT_OPTIONS":""}
    
    r = requests.post(postURL, data=postfields, cookies=cookie)
    
    f = r.text
    
    soup = BeautifulSoup(f)
    
    if f.find("No available course section(s)") > 0:
        return "Error: Course not found"
    
    table = soup.find('table', attrs={'class':'mainTable'})
    rows = table.findAll('tr')[5:]

    h = HTMLParser()
    
    courseObjects = []
    
    for row in rows:
        Course = {}
        Section = {}
        
        cols = row.findAll('td')
        
        title = h.unescape(cols[3].find('a').contents[0])
        
        Code = "*".join(title.split("*")[:2])
        
        spots = cols[7].find('p').contents[0] #spots
        Meeting_Section = title.split("*")[2].split(" ")[0]
        
        #don't include closed courses
        #############################################################
        if spots == '\n' or cols[2].getText() == 'Closed':
            continue
        #############################################################
                
        courseIndex = findIndex(courseObjects, Code)
        
        if courseIndex == -1:
            
            Name = " ".join(title.split(" ")[2:]) #backup if info is not found on course

            Level = cols[10].find('p').contents[0] #level (not really) (Undergraduate / Graduate) (Level not mentioned)
            
            extraInfo = getDescription(Code, Level)
            
            Description = extraInfo['Description']
            
            if 'Prerequisites' in extraInfo:
                Prerequisites = extraInfo['Prerequisites']
            else:
                Prerequisites = ""
            
            if 'Exclusions' in extraInfo:
                Exclusions = extraInfo['Exclusions']
            else:
                Exclusions = ""
            
            if 'Offerings' in extraInfo:
                Offerings = extraInfo['Offerings']
            else:
                Offerings = ""
            
            if len(extraInfo['Name']) > len(Name):
                Name = extraInfo['Name']
            
            Campus = cols[4].find('p').contents[0] #campus
            Num_Credits = cols[8].find('p').contents[0] #credits
            
            Course['Course'] = Code
            Course['Name'] = Name
            Course['Description'] = Description
            Course['Campus'] = Campus
            Course['Prerequisites'] = Prerequisites
            Course['Exclusions'] = Exclusions
            Course['Offerings'] = Offerings
            Course['Num_Credits'] = Num_Credits
            Course['Level'] = Level
            Course['Sections'] = []
        
        Instructors = cols[6].find('p').contents[0] #prof
        
        Size = spots.split(' / ')[1]
        Enrollment = spots.split(' / ')[0]
        
        Section['Course'] = Code
        Section['Meeting_Section'] = Meeting_Section
        Section['Size'] = Size
        Section['Enrollment'] = Enrollment
        Section['Instructors'] = Instructors
        Section['Semester'] = SEMESTER
        
        Offering = []
        
        for x in cols[5].find('p').contents[0].split('\n'): #meeting info
            tempObject = {}
            
            splitX = x.split(' ')
            
            if x.find('-', 11) == -1:
                continue
            
            indexOfHyphon = splitX.index('-')
            
            Section_Type = splitX[1] #session type
            Day = ' '.join(splitX[2:indexOfHyphon-1]) #days
            Location = splitX[-3] + " room " + splitX[-1] # room number
            
            startTime = splitX[indexOfHyphon-1] #start time
            endTime = splitX[indexOfHyphon+1].replace(',', '') #end time
            
            tempObject['Course'] = Code
            tempObject['Section_Type'] = Section_Type
            tempObject['Day'] = Day
            tempObject['Time_Start'] = convertTime(startTime)
            tempObject['Time_End'] = convertTime(endTime)
            tempObject['Location'] = Location
            
            Offering.append(tempObject)
        
        Section['Offerings'] = Offering
        
        if courseIndex == -1:
            courseObjects.append({'Course':Course})
            courseObjects[-1]['Course']['Sections'].append(Section)
        else:
            courseObjects[courseIndex]['Course']['Sections'].append(Section)
        #, {'Section':Section}, {'Offering':Offering}]
    
    
    return courseObjects
    #with open('data.txt', 'w') as outfile:
    #    json.dump(courseObjects, outfile)

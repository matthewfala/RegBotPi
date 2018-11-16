# coding: utf-8

# In[1]:


# Beautiful Soup Tests


# In[2]:


from bs4 import BeautifulSoup
import lxml
from lxml import html
import requests
import CoursePlan
import Settings

# In[3]:

class course:
    def __init__(self, name, section, time, availible, scheduled, registered):
        self.name = name
        self.department = name.split("-")[0];
        # print(self.department)
        self.section = int(section)
        self.time = time
        self.availible = availible
        self.scheduled = scheduled
        self.registered = registered
        # print("Course " + str(self.section) + " created")

    def unschedule(self, s):
        if self.scheduled:
            domain = "https://webreg.usc.edu"
            req = domain + "/myCoursebin/SchdUnschRmv?act=UnSched&section=" + str(self.section)
            s.get(req)
            self.scheduled = False
            print("Unscheduled with: " + req)

    def schedule(self, s):
        if not self.scheduled:
            domain = "https://webreg.usc.edu"
            req = domain + "/myCoursebin/SchdUnschRmv?act=Sched&section=" + str(self.section)
            s.get(req)
            self.scheduled = True
            print("Scheduled with: " + req)

    def tobin(self, s):
        payload = {
            # X-Requested-With: XMLHttpRequest
            "conccourseid": "",
            "courseid": self.name,
            "department": self.department,
            "grdoptchgflg": "N",
            "sectionid": self.section,
            "unitselect": ""
        }

        cbinadd_url = "https://webreg.usc.edu/myCoursebin/SubmitSection"
        session.post(cbinadd_url, data=payload)
        self.scheduled = True

        self.unschedule(s)


# In[5]:


# Login

# Returns session
def usc_auth(username, password):
    s = requests.Session()
    r = s.get('https://my.usc.edu/')

    enter_page = lxml.html.fromstring(r.content)
    form_1 = enter_page.xpath("//form[@name='form1']")
    # print form_1[0].attrib['action']

    Query = "https://shibboleth.usc.edu" + form_1[0].attrib['action']
    # print Query
    payload = {'_eventId_proceed': '', 'shib_idp_ls_exception.shib_idp_persistent_ss': '',
               'shib_idp_ls_exception.shib_idp_session_ss': '',
               'shib_idp_ls_success.shib_idp_persistent_ss': 'false',
               'shib_idp_ls_success.shib_idp_session_ss': 'false',
               'shib_idp_ls_supported': '',
               'shib_idp_ls_value.shib_idp_persistent_ss': '',
               'shib_idp_ls_value.shib_idp_session_ss': ''
               }

    bypass = s.post(Query, data=payload)

    payload = {
        '_eventId_proceed': '',
        'j_password': password,
        'j_username': username
    }

    login = s.post(bypass.url, data=payload)
    tree = lxml.html.fromstring(login.content)

    SAMLResponses = tree.xpath("//form//input[@name='SAMLResponse']")
    SAMLResponse = SAMLResponses[0].attrib['value']

    payload = {'SAMLRequest': SAMLResponse}
    login = s.post('https://my.usc.edu/portal/Shibboleth.sso/SAML2/POST', payload)

    print("Are We Logged In? : " + str(username in login.text))
    if username not in login.text:
        raise Exception("Login Error")
    return s


# In[6]:


import pickle
import os
import re

pickle_file = 'my_usc_session.pkl'
term = 'spring'  # Options, Spring Fall Summer

home = 'https://my.usc.edu/'
webreg_connect = 'https://my.usc.edu/portal/oasis/webregbridge.php'
webreg = "https://webreg.usc.edu/"


def new_saved_session(_pickle_file):
    print("No pickle file, generating new session")
    with open(_pickle_file, 'wb') as output:
        s = usc_auth(credentials.get_username(), credentials.get_password())
        pickle.dump(s, output, pickle.HIGHEST_PROTOCOL)
        print("Logged In")


def recover_session(_pickle_file):
    with open(_pickle_file, 'rb') as myinput:
        print("File exists! recovering session ...")
        recovered_s = pickle.load(myinput)
        return recovered_s


# returs session
def webreg_login():
    # Save and recover session
    if not os.path.isfile(pickle_file):
        new_saved_session(pickle_file)
    try:
        s = recover_session(pickle_file)
    except:
        print("Recovery failed.")
        s = new_saved_session(pickle_file)

    terms_page = s.get(webreg_connect)

    session_end_phrase = 'Your session has ended.'
    session_ended = session_end_phrase in terms_page.text

    if session_ended:
        print("Session ended, forcing new session")
        # force new session
        new_saved_session(pickle_file)
        s = recover_session(pickle_file)
        terms_page = s.get(webreg_connect)

    tree = lxml.html.fromstring(terms_page.content)

    if term == 'fall':
        term_element = tree.xpath("//ul//li[@id='termmenuFall']/a")
    elif term == 'summer':
        term_element = tree.xpath("//ul//li[@id='termmenuSumm']/a")
    elif term == 'spring':
        term_element = tree.xpath("//ul//li[@id='termmenuSpr']/a")

    addr = webreg + term_element[0].attrib['href']
    catalogue = s.get(addr)
    return s


# In[7]:


def simplify_schedule(s, courses):
    change_log = set()
    for key, c in courses.items():
        if c.registered:
            if not c.scheduled:
                c.schedule(s)
                change_log.add((c, "Scheduled"))

        elif not c.registered:
            if c.scheduled:
                c.unschedule(s)
                change_log.add((c, "Unscheduled"))

    return change_log


def restore_schedule(s, change_log, ignore):
    for c in change_log:
        if c[0] in ignore:
            print("Successfully ignored course")
            continue
        if c[1] == "Scheduled":
            c[0].unschedule(s)
        elif c[1] == "Unscheduled":
            c[0].schedule(s)


def register(s, dropped):
    payload = {
        'Origin': 'https://webreg.usc.edu',
        'Upgrade-Insecure-Requests': '1',
    }
    s.get("https://webreg.usc.edu/Register")
    r = s.post("https://webreg.usc.edu/RegResp", data=payload)
    # print(r.text)
    if "Registration Failed" in r.text:
        print("Registration failure")
        return # exit registration
    else:
        print("Registration success")

    # Add back dropped courses into course bin
    for d in dropped:
        d.tobin(s)


# In[8]:


# Login
import credentials


def login():
    # session = usc_auth(credentials.get_username(), credentials.get_password())
    global session
    global report

    for i in range(0, 3):
        try:
            session = webreg_login()
            report = course_report(session)
            # for c in report:
            #    print(c.section)
            print("Done.")
            break
        except:
            print("Failed login. Retrying. Attempt: " + str(i + 1))


# In[9]:


# Poll Courses
# get request to "/myCoursebin/SchdUnschRmv?act=UnSched&section=<MYSECTION>"

def course_report(s):
    r = s.get("https://webreg.usc.edu/myCourseBin")
    soup = BeautifulSoup(r.text, "lxml")
    courses = dict()
    course_data0 = soup.find_all(class_="section_crsbin_alt0")
    course_data1 = soup.find_all(class_="section_crsbin_alt1")
    course_data2 = soup.find_all(class_="section_crsbin_alt2")

    course_data = course_data0 + course_data1 + course_data2

    for c in course_data:

        name = c.parent.parent.parent.find("input", id="Course")["value"]

        section_full = str(c.contents[3].contents[1].string)
        section = section_full.split(' ', 1)[0]
        availible = "Closed" not in c.contents[11].contents[1].string

        time = c.contents[13].contents[1].string

        status_sY_rN = "block" in c.contents[1].contents[2]['style']
        status_sN_rN = "block" in c.contents[1].contents[4]['style']
        status_sY_rY = "block" in c.contents[1].contents[6]['style']
        status_sN_rY = "block" in c.contents[1].contents[8]['style']

        if status_sY_rN:
            scheduled = True
            registered = False
        elif status_sN_rN:
            scheduled = False
            registered = False
        elif status_sY_rY:
            scheduled = True
            registered = True
        elif status_sN_rY:
            scheduled = False
            registered = True
        else:
            print("An error has ouccured, course bin class " + str(section) + " is corrupt")

        # print ("Section: " + section)
        # print ("Avalible: " + str(availible))
        # print ("Time: " + time)
        # print ("Scheduled: " + str(scheduled))
        # print ("Registered: " + str(registered))
        courses[int(section)] = course(name, section, time, availible, scheduled, registered)
        # print ()
        # print(name)
        # .find("input", id="Course")

    return courses


# my_report = course_report(session)


# In[10]:


# change_log = simplify_schedule(session, report)


# In[11]:


# restore_schedule(session, change_log, [])


# In[12]:


class registrar:

    # modes: priority, combo
    # priority [ [ [c,c,c],[c,c,c] ],  ]
    # combos: [ [c, c, c ], ]
    def __init__(self, desireable_combos, mode):
        # Needs combo blacklist implementation
        self.desireable_combos = desireable_combos
        self.mode = mode
        # we definitely need some sort of key check

    def schedule_ops(self, report):
        if (self.mode == "priority"):
            return self.schedule_ops_priority(report)
        if (self.mode == "combos"):
            return self.schedule_ops_combos(report)

    # returns [ drop, register ]
    def schedule_ops_priority(self, report):
        drop = set()
        register = set()

        for combo in self.desireable_combos:

            all_reqs_met = True
            for req in combo:
                req_met = False
                for sec in req:
                    # don't update if higher priority is registered
                    if report[int(sec)].registered:

                        # new register
                        if req_met == True:
                            drop.add(sec)
                            print("Dropping: " + str(req))

                        # maintain
                        req_met = True
                        break

                    if report[int(sec)].availible:
                        if not req_met:
                            register.add(sec)
                            print("Adding: " + str(sec))
                        req_met = True

                if not req_met:
                    all_reqs_met = False
                    print("No class was found from the required course set: " + str(req))
                    break

            # only features 1 combo at the moment
            if all_reqs_met:
                return ([drop, register])

            return [[], []]

    # combos [ [[c, c, c ], [c,c,c]], [[c, c, c ], [c,c,c]] ]
    def schedule_ops_combos(self, report):

        drop = set()
        register = set()

        # find enrolled courses
        cur_reg = set()
        for key, r in report.items():
            if r.registered:
                cur_reg.add(r)
                # print("Enrolled: " + str(r.section))

        for comboset in self.desireable_combos:

            # comboset = [ [c,c,c], [c,c,c] ]
            all_combo_sections = set();
            for combo in comboset:
                for sec in combo:
                    all_combo_sections.add(report[int(sec)])
                    # print("Combo " + str(combo) + ": " + str(sec))
            # print(str(all_combo_sections))

            combo_found = False
            combo_register = set()
            for combo in comboset:

                combo_satisfied = True
                for sec in combo:

                    if report[int(sec)].registered:
                        continue
                    elif report[int(sec)].availible:
                        continue

                    combo_satisfied = False
                    # print("No class was found from the required course set: " + str(sec))
                    break

                if combo_satisfied:
                    for sec in combo:
                        # if not report[int(sec)].registered:
                        combo_register.add(report[int(sec)])
                    combo_found = True

                    # console output
                    print("Potential Course Plan: " + str(combo))
                    break

            if combo_found:
                register.update(combo_register.difference(cur_reg))
                combo_inferior = all_combo_sections.difference(combo_register)
                drop.update(cur_reg.intersection(combo_inferior))

        return [drop, register]

    def auto_reg(self, s):

        report = course_report(s)
        [drop, reg] = self.schedule_ops(report)

        # console output
        if len(reg) == 0 and len(drop) == 0:
            print("Course plan is currently optimal.")
        if len(reg) > 0:
            print("Registering for Courses: " + str(list(reg)))
        if len(drop) > 0:
            print("Dropping Courses: " + str(list(drop)))

        self.attempt_reg(session, reg, drop, report)

    def attempt_reg(self, s, reg_courses, drop_courses, all_courses):

        # setup
        change_log = simplify_schedule(s, all_courses)
        reg_needed = False

        # add courses
        for course in reg_courses:
            print("Scheduling: " + str(course.section))
            if course.availible and not course.registered:
                course.schedule(s)
                reg_needed = True

        # drop courses
        for course in drop_courses:
            print("Dropping: " + str(course.section))
            if course.registered:
                course.unschedule(s)
                reg_needed = True

        # register
        if reg_needed:
            print("Attempting registration ...")
            register(s, drop_courses)

        # cleanup
        # print("Reg Courses Size: " + str(len(reg_courses)))

        restore_schedule(s, change_log, reg_courses)

    def find_courses(self, all_courses, sections):
        courses = set()
        for c in all_courses:
            if int(c.section) in sections:
                courses.add(c)
        return courses


# In[ ]:


from time import sleep
import time
import random

# Crapo Timer
print("######################################################")
print("##              Starting RegBot 1.0...              ##")
print("######################################################")
bot_start_time = time.time()

# import course plan
my_combos = CoursePlan.my_combos
course_attempt = 1

def crap_bot(course_plan):
    # print ("Running " + str(newinterval))
    print("Time Elapsed: " + str(time.time() - bot_start_time))
    # print ("Attempt: " + str(course_attempt))
    print("Random Wait: " + str(newinterval))
    # course_attempt = course_attempt + 1


def reg_bot(course_plan):
    global course_attempt
    print("###################################################")
    print("Time Elapsed: " + str(time.time() - bot_start_time))
    print("Attempt: " + str(course_attempt))
    print("Random Wait: " + str(newinterval))
    print("-------------")
    course_attempt = course_attempt + 1

    try:
        # work on black list, & individual combo reg
        login()
        bot_registrar = registrar(course_plan, "combos")
        bot_registrar.auto_reg(session)

    except:
        print("An error has occurred")


while True:
    # Randomized time settings
    ave_time = Settings.average_delay_time
    pm_time = Settings.sd_delay_time

    newinterval = random.randint(ave_time - pm_time, ave_time + pm_time)
    reg_bot(my_combos)

    time.sleep(newinterval)

# In[ ]:


# DONE


# In[ ]:


# work on black list, & individual combo reg

# login()
# course_plan = [[ [39628, 39629], [39628, 39630], [39625, 39626], [41809, 41813],  [39625,39627], [49446], [10112] ] ]
# bot_registrar = registrar(course_plan,  "combos")
# bot_registrar.auto_reg(session)


# combos test: [[ [39628, 39629], [39628, 39630], [39625, 39626], [39625,39627], [21911, 21912], [30396, 30269, 30224] ] ]
# priority: [ [[39625, 39628, 21911 ], [39626, 39627, 39629, 39630, 21912 ]] ]

#
# {{[], []} {} {} }
# desired->requirements, choose 1 of each, priority to smaller indexs
# reg.auto_reg(session)


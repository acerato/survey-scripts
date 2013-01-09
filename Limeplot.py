""" Limeplot

A script to parse, analyze and graph exported responses from LimeSurvey.

This script was originally written for the Open Internet Tools Project, as part
of a research survey about censorship circumvention tool usage in China. As such,
some of this code is purpose-built (for now) to analyze the data we have.

http://www.openitp.org

"""

__version__ = "0.8"
__copyright__ = "Copyright (c) 2012-2013 Open Internet Tools Project"
__license__ = "GPLv3"

import colorsys
import csv
import random
import re
import time

from bs4 import BeautifulSoup

import numpy as np
import matplotlib
import matplotlib.pyplot as plt


font = {'family' : 'normal',
        'size'   : 10}
matplotlib.rc('font', **font)

#colormap = plt.cm.gist_ncar

class Limeplot:

    def __init__(self, structure, responses, main_seeds=['*']):
        """ Plot Limesurvey responses.

            'main_seeds' is a list of root seed values, each of which
              will be plotted separately. The value '*' denotes all
              remaining responses, not contained in any existing seed group

        """


        # Dictionary of survey questions
        #  name -> (qid, question_text, type, mandatory, other)
        #  e.g. questions["life"] -> ("119", "Where have you lived...?", "L", 
        #                             True, False)
        self.questions = {}

        # Dictionary of survey subquestions
        #  (qid, title) -> (subquestion_text, mandatory)
        #  e.g. subquestions[("125", "SQ003")] -> ("Paid VPN", True)
        self.subquestions = {}

        # Dictionary of survey answers
        #  qid x code -> answer_text
        #  e.g. answers["119"]["A1"] == "In mainland China"
        self.answers = {}

        self.get_structure(structure)
        self.get_responses(responses)

        self.main_seeds = main_seeds

    def get_qid_from_qname(self, qname):
        return self.questions[qname][0]

    def get_qtext_from_qname(self, qname):
        return self.questions[qname][1]

    def get_qtype_from_qname(self, qname):
        return self.questions[qname][2]

    def is_qname_mandatory(self, qname):
        return self.questions[qname][3]

    def is_qname_other(self, qname):
        return self.questions[qname][4]

    def get_subqtext(self, qid, title):
        return self.subquestions[(qid, title)][0]

    def is_subqname_mandatory(self, qid, title):
        return self.subquestions[(qid, title)][1]

    def _convert_yn_to_bool(self, yn):
        """ Convert "Y" or "N" string to booleans. """

        if yn == "Y":
            return True
        elif yn == "N":
            return False
        else:
            raise Exception, "_convert_yn_to_bool: " + yn

    def get_responses(self, filename):
        """ Parse the response rows out of the .csv export file.
        
            In Limesurvey, choose export options:
            - Completion state: Completed responses only
            - Headings: Question code 
            - Responses: Answer code
              - Convert Y/N 
            - CSV
            
        """

        with open(filename) as data:
            reader = csv.reader(data)
            self.responses = [row for row in reader]

    def get_structure(self, filename):
        """ Parse the survey structure out of the .lss export file. """

        with open(filename) as xml:
            soup = BeautifulSoup(xml.read(), "xml")

            question_rows = soup.document.questions.rows
            for row in question_rows.find_all("row"):
                if row.language.string == "en":
                    question_text = row.question.string.strip()
                    qid = row.qid.string
                    type = row.type.string
                    mandatory = self._convert_yn_to_bool(row.mandatory.string)
                    other = self._convert_yn_to_bool(row.other.string)
                    question_text = BeautifulSoup(question_text).text
                    question_text = question_text.split("\n")[-1] # Get rid of js

                    self.questions[row.title.string] = \
                        (qid, question_text, type, mandatory, other)

            subquestion_rows = soup.document.subquestions.rows
            for row in subquestion_rows.find_all("row"):
                if row.language.string == "en":
                    subquestion_text = row.question.string.strip()
                    parent_qid = row.parent_qid.string
                    # mandatory = self._convert_yn_to_bool(row.mandatory.string)
                    # TK mandatory. All subq mandatory fields are false?
                    mandatory = False
                    title = row.title.string

                    self.subquestions[(parent_qid, title)] = \
                        (subquestion_text, mandatory)

            answer_rows = soup.document.answers.rows
            for row in answer_rows.find_all("row"):
                if row.language.string == "en":
                    answer_text = row.answer.string.strip()
                    qid = row.qid.string
                    code = row.code.string

                    try:
                        self.answers[qid][code] = answer_text
                    except KeyError:
                        self.answers[qid] = {}
                        self.answers[qid][code] = answer_text


    def filter_columns_by_name(self, filterstr, responses, show_other=False):
        """
        Return the response columns that begin with 'filterstr'.
        
        By default, the show_other parameter ignores the "other" column 
        for write-in answers.

        Also ignores all "Time*" columns (hardcoded).    

        """

        header = responses[0]

        matched = []
        filter = re.compile("^"+filterstr)
        other_filter = re.compile("\xe5\x85\xb6\xe5\xae\x83")
        time = re.compile("Time$")

        for index in range(len(header)):
            item = header[index]
            if filter.search(item):
                if (not show_other and other_filter.search(item)) \
                        or time.search(item):
                    continue
                matched.append(index)

        responses = [[response[i] for i in matched] for response in responses]
    
        return responses
    
    def filter_rows_by_seed(self, seed, responses):
        """ Return the response rows that are descendents of 'seed'. """

        header = responses[0]

        ref_index = header.index("ref")
        unique_index = header.index("unique")

        seed_sets = []

        # Populate seed sets
        for response in responses[1:]:
            ref = response[ref_index]
            unique = response[unique_index]

            if len(unique) != 4:
                continue

            added = False
            for seed_set in seed_sets:
                if ref in seed_set:
                    seed_set.add(unique)
                    added = True
                          
            if not added:
                seed_sets.append(set([ref, unique]))

        results = [header]
        if seed == "*":
            for seed_set in seed_sets:
                if not seed_set & set(self.main_seeds):
                    for response in responses[1:]:
                        ref = response[ref_index]
                        if ref in seed_set:
                            results.append(response)
        else:
            for seed_set in seed_sets:
                if seed in seed_set:
                    for response in responses[1:]:
                        ref = response[ref_index]
                        if ref in seed_set:
                            results.append(response)
                    break

        return results

    def _clean_integer(self, s):
        try:
            return int(s)
        except ValueError:
            return 0


    def plot_array_boxes(self, qname, responses):
        """ Plot array question, e.g.:
            - computerphone
            - recenttools
        """

        header = responses[0]

        qid = self.get_qid_from_qname(qname)
        
        answers = self.answers[qid].keys()
        answers.sort()

        tally = [[0]*len(answers) for i in header]

        for response in responses[1:]:
            if response.count("") == len(header):
                continue

            for index in range(len(header)):
                answer = response[index]
                tally[index][answers.index(answer)] += 1

        tallypct = []
        for t in tally:
            total = sum(t)
            tallypct.append(["%.1f" % (float(x)/total*100) for x in t])

        # TK: draw bar graphs. Pretty print text for now.
        print "\t\t",
        for a in answers:
            print "%s\t" % self.answers[qid][a],
        print ""

        index = 0
        for heading in header:
            split = heading.split(" ")
            qtitle = split[1].strip("[]")
            qtext = self.get_subqtext(qid, qtitle)

            print qtext,
            for t in tallypct[index]:
                print t + "%\t",
            print ""

            index += 1
                

    def plot_convergence_numerical(self, responses):
        """ Plot numerical questions, i.e. age """
        header = responses[0]

        bucket_size = 5
        arbitrary_min = 10
        arbitrary_max = 69

        max_response = max([int(float(x[0])) for x in responses[1:]])
        max_response = min(max_response, arbitrary_max)
        num_buckets = (max_response - arbitrary_min) / bucket_size + 1

        tally = [0]*num_buckets
        lines = []

        for response in responses[1:]:

            answer = int(float(response[0]))
            
            # Ignore responses greater than the arbitrary min and max
            if answer > arbitrary_max or answer < arbitrary_min:
                continue

            bucket_num = (int(float(response[0]))-arbitrary_min) / bucket_size

            tally[bucket_num] += 1

            total = float(sum(tally))

            index = 0
            for t in tally:
                percent = 0.0
                try:
                    percent = float(t)/total
                except ZeroDivisionError:
                    pass

                try:
                    lines[index].append(percent)
                except IndexError:
                    lines.append([0.0, percent])
                index += 1

        legend = ["%d to %d" % (x, x+bucket_size-1) \
                      for x in range(arbitrary_min, max_response, bucket_size)]

        for line in lines:
            plt.plot(line, scaley=False)
            plt.xlabel("First n Samples")
            plt.ylabel("Cumulative Frequency")
            plt.legend(legend, loc='upper left', prop={'size':8})


    def plot_convergence_radio(self, qname, responses):
        """ Plot radio-type questions, e.g.:
            - city
            - gender
            - preference
            - education
            - job
            - travel
            - life
            
        """

        header = responses[0]

        qid = self.get_qid_from_qname(qname)

        if self.get_qtype_from_qname(qname) == "G":
            answers = ["M", "F"]
        else:
            answers = self.answers[qid].keys()
            answers.sort()

        if not self.is_qname_mandatory(qname) or self.is_qname_other(qname):
            answers.append("")

        tally = [0]*len(answers)
        lines = []

        for response in responses[1:]:
            response = response[0]
            tally[answers.index(response)] += 1

            total = float(sum(tally))

            index = 0
            for t in tally:
                percent = 0.0
                try:
                    percent = float(t)/total
                except ZeroDivisionError:
                    pass

                try:
                    lines[index].append(percent)
                except IndexError:
                    lines.append([0.0, percent])
                index += 1

        legend = []
        for answer in answers:
            qid = self.get_qid_from_qname(header[0])
            try:
                atext = self.answers[qid][answer]
            except KeyError:
                atext = "No answer"

                if self.get_qtype_from_qname(qname) == "G":
                    if answer == "M":
                        atext = "Male"
                    elif answer == "F":
                        atext = "Female"
                    else:
                        pass

            legend.append(atext)

        for line in lines:
            plt.plot(line, scaley=False)
            plt.xlabel("First n Samples")
            plt.ylabel("Cumulative Frequency")
            plt.legend(legend, loc='upper left', prop={'size':8})

    def plot_convergence_checkbox(self, responses):
        """ Plot checkbox-type questions, e.g.:
            - evertools
            - reasons
            - mostoftenwhy
            - problems
            - help
            - firstlearn
            - nouse
            
        """

        header = responses[0]
        tally = [0]*len(header)
        lines = []

        for response in responses[1:]:
            response = [self._clean_integer(s) for s in response]

            if sum(response) == 0:
                continue

            tally = [t+r for (t,r) in zip(tally,response)]

            total = float(sum(tally))
        
            index = 0
            for t in tally:
                percent = 0.0
                try:
                    percent = float(t)/total
                except ZeroDivisionError:
                    pass

                try:
                    lines[index].append(percent)
                except IndexError:
                    lines.append([0.0, percent])
                index += 1

        legend = []
        for heading in header:
            split = heading.split(" ")

            qname = split[0].strip()
            qid = self.get_qid_from_qname(qname)

            qtitle = split[1].strip("[]")
            qtext = self.get_subqtext(qid, qtitle)
            legend.append(qtext)
        

        for line in lines:
            plt.plot(line, scaley=False)
            plt.xlabel("First n Samples")
            plt.ylabel("Cumulative Frequency")
            plt.legend(legend, loc='upper right', prop={'size':8})

            #colors = [colormap(i) for i in np.linspace(0, 0.9, len(legend))]
            #plt.gca().set_color_cycle(colors)

    
    def plot_main_seeds(self, qname, radio=False, checkbox=False, 
                        numerical=False, array=False):
        """ Plot the responses separately for each seed group in main_seeds. """
        
        assert sum([radio, checkbox, numerical, array]) == 1

        for seed in self.main_seeds:
            responses_seed = self.filter_rows_by_seed(seed, self.responses)
            responses_seed_question = self.filter_columns_by_name(qname, responses_seed)

            plt.subplot(int("22" + str(self.main_seeds.index(seed))))
            plt.title("Seed " + seed)

            if radio:
                self.plot_convergence_radio(qname, responses_seed_question)
            elif checkbox:
                self.plot_convergence_checkbox(responses_seed_question)
            elif numerical:
                self.plot_convergence_numerical(responses_seed_question)
            elif array:
                self.plot_array_boxes(qname, responses_seed_question)

        qtext = self.get_qtext_from_qname(qname)
        plt.suptitle(qtext)
        plt.tight_layout()
        plt.show()

    def _get_colors(self, num):
        """ Ick. Not done.

        """

        hsv = [(float(i)/num, 0.5, 0.5) for i in range(num)]
        rgb = [colorsys.hsv_to_rgb(*x) for x in hsv]
        print rgb
        rgb = [format((int(x[0]*256)<<16)|(int(x[1]*256)<<8)|int(x[2]*256), '06x') for x in rgb]
        print rgb


    def plot(self, qname):
        """ Plot the question using the appropriate question type handler. """

        if qname in ["city", "gender", "preference", "education", "job", \
                         "travel", "life"]:
            self.plot_main_seeds(qname, radio=True)
        elif qname in ["evertools", "reasons", "mostoftenwhy", "problems",\
                           "help", "firstlearn", "nouse"]:
            self.plot_main_seeds(qname, checkbox=True)
        elif qname == "age":
            self.plot_main_seeds(qname, numerical=True)

        elif qname in ["computerphone", "recenttools"]:
            self.plot_main_seeds(qname, array=True)
        else:
            raise Exception, "Unknown question name."

    def _get_timestamp(self, timestring):
        split = timestring.split()
        date_yyyy, date_mm, date_dd = [int(x) for x in split[0].split("-")]
        time_hh, time_mm, time_ss = [int(x) for x in split[1].split(":")]

        timestamp = time.mktime((date_yyyy, date_mm, date_dd,
                                 time_hh, time_mm, time_ss,
                                 0,0,0))       
        return timestamp


    def plot_time(self, responses):
        """ Plot the rate of incoming responses, by seed """
        
        bin_size = 1800
        min_time = self._get_timestamp(responses[1][5])

        lines = []

        for seed in self.main_seeds:
            seed_responses = self.filter_rows_by_seed(seed, responses)

            bins = []
            for r in seed_responses[1:]:
                timestring = r[5]
                timestamp = self._get_timestamp(timestring)

                delta = timestamp - min_time
                bin = int(delta/bin_size)
                bins.append(bin)

            line = []
            for i in range(max(bins)):
                line.append(bins.count(i))
            lines.append(line)

        for line in lines:
            plt.plot(line)
        plt.xlabel("Time (%d min bins)" % (bin_size/60))
        plt.ylabel("Responses")
        plt.legend(self.main_seeds, loc='upper left', prop={'size': 8})
        plt.show()


    def plot_interview_length(self, responses):

        times = []
        for r in responses[1:]:
            times.append(float(r[88]))

        plt.hist(times, bins=300)
        plt.show()


if __name__ == "__main__":

    structure_file = "limesurvey_survey_228555.lss"
    responses_file = "all-1133.csv"
    main_seeds = ["G61n", "x0GW", "*"]

    survey = Limeplot(structure_file, responses_file, main_seeds)
    survey.plot("problems")
    #survey.plot_time(survey.responses)
    #survey.plot_interview_length(survey.responses)

    # TK: fix plot array boxes

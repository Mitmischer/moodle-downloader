#!/usr/bin/python3
import mechanicalsoup
import os
from tqdm import tqdm
import math
import logging

import configparser

from multiprocessing import Process
from threading import Thread
import time
import click

import datetime


# winter semester: oct to mar
# summer semester: apr to sep
def current_semester_as_string(today):
    ws_strings = ["WiSe{}", "WS {}"]
    ss_strings = ["SoSe{}"]

    strings = []
    short_year = today.year - 2000
    if short_year < 0:
        raise TypeError("invalid year")

    # summer semester
    if 3 < today.month < 10:
        for s in ss_strings:
            strings.append(s.format(short_year))
    # winter semester
    else:
        if today.month <= 3:
            short_year = short_year - 1
        for s in ws_strings:
            strings.append(s.format(str(short_year)+"_"+str(short_year+1)))

    return strings

@click.command()
@click.option("--include-old-semesters", is_flag=True, help="Specify the flag if all semester should be downloaded (not only the current one).")
def main(include_old_semesters):
    logging.basicConfig(format='(%(levelname)s) %(message)s')

    conf = configparser.ConfigParser()
    conf.read("config.ini")

    if not os.path.exists("files"):
        os.mkdir("files")
    os.chdir("files")
    root_dir = os.getcwd()

    # login
    print("Connecting to moodle...")
    browser = mechanicalsoup.StatefulBrowser()
    browser.open("https://moodle.ruhr-uni-bochum.de/m/")
    print(" Done.")
    
    print("Performing login...")
    browser.select_form('form[class="loginform"]')
    browser["username"] = conf.get("auth", "username")
    browser["password"] = conf.get("auth", "password")
    response = browser.submit_selected()
    print(" Done.")

    course_urls = []
    for item in browser.get_current_page().find_all("h3", class_="coursename"):
        # the h3 only contains one anchor
        anchor = item.find_all("a")[0]
        # "defuse" the course name, such that only legal file names are obtained.
        print("Found course {0} ({1})".format(item.text.replace("/", "_"), anchor["href"]))
        course_urls.append((anchor["href"], item.text.replace("/", "_")))

    semester_strings = current_semester_as_string(datetime.date.today())

    for url, coursename in course_urls:
        os.makedirs(coursename, exist_ok=True)
        os.chdir(coursename)

        found = True

        if not include_old_semesters:
            found = False
            for s in semester_strings:
                if coursename.find(s) > -1:
                    found = True
                    break
        if not found:
            print(" Ignoring course room {} (not current semester)".format(coursename))
            continue

        print(" Processing course room {}".format(coursename))
        browser.open(url)

        resource_urls = []
        # Case 1: Files are not organized
        resources =  browser.get_current_page().find_all("li", class_="resource")
        for res in resources:
            activityinstance = res.find("div", class_="activityinstance")

            # strings[0] instead of text is used as the tag contains another tag with text that should not be included.
            res_name = list(activityinstance.find("span", class_="instancename").strings)[0].replace("/", "_")
            # Find suffix based on the picture
            picture = activityinstance.find("img", class_="activityicon")
            if "pdf" in  picture["src"]:
                res_name += ".pdf"
            elif "mpeg" in picture["src"]:
                res_name += ".mpeg"
            elif "htm" in picture["src"]:
                res_name += ".html"
                print("  (warning) Ignoring html file {0}".format(res_name))
                continue
            else:
                print("  (warning) Could not determine resource type for {0}".format(res_name))

            # is the activity restricted?
            restricted_tag = res.find("div", class_="isrestricted")
            if restricted_tag:
                print("  (info) Ignoring resource {0} which is restricted".format(res_name))
                continue

            anchor = res.find("a")
            if not anchor:
                print("Error: Could not process activityinstance")
                print(activityinstance)
                continue

            # redirect=1 skips the download page
            resource_urls.append( (anchor["href"]+"&redirect=1", res_name.replace("/", "_")) )

        # Case 2: Files are organized in a "filemanager" structure.
        filemanagers = browser.get_current_page().find_all("div", class_="filemanager")
        for filemanager in filemanagers:
            filename_icons = filemanager.find_all("span", class_="fp-filename-icon")
            for filename_icon in filename_icons:
                anchor = filename_icon.find("a")
                url = anchor["href"]
                filename = anchor.find("span", class_="fp-filename").text
                resource_urls.append( (url, filename) )

        # Download all found resources.
        threads = []
        # 3 concurrent connections
        free_is = [0,1,2]
        resource_urls = [ru for ru in resource_urls if not os.path.exists(ru[1])]
        if resource_urls:
            tqdm.write("  Downloading {0} file(s)...".format(len(resource_urls)))
        for resource_url in resource_urls:
            if os.path.exists(resource_url[1]):
                # skip file, it has a local copy already
                continue

            i = free_is.pop(0)
            t = Thread(target=download_file, args=(browser, resource_url, i))
            t.start()
            threads.append( (t, i) )

            while len(threads) == 3:
                for (t, i) in threads:
                    if not t.is_alive():
                        free_is.append(i)

                threads[:] = [(t, i) for (t, i) in threads if t.is_alive()]

                time.sleep(0.1)

        for (t,_) in threads:
            t.join()

        # Case 3: Files are organized in folders (=> structurally in different course rooms)
        subfolders = browser.get_current_page().find_all("li", class_="folder")
        for subfolder in subfolders:
            activityinstance = subfolder.find("div", class_="activityinstance")
            restricted_tag = subfolder.find("div", class_="isrestricted")
            res_name = list(activityinstance.find("span", class_="instancename").strings)[0]
            if restricted_tag:
                print("  (info) Ignoring folder {0} which is restricted".format(res_name))
                continue

            anchor = activityinstance.find("a")
            url = anchor["href"]

            foldername = list(activityinstance.find("span").strings)[0].replace("/", "_")
            print("  Found subfolder {0} ({1})".format(foldername, url))
            # use the parent course name for structure.
            course_urls.append( (url, coursename+"/"+foldername) )

        print("  Done.")

        os.chdir(root_dir)


def download_file(browser, resource_url, position):
    try:
        r = browser.session.get(resource_url[0], stream=True)

        total_size = int(r.headers.get('content-length', 0))
        wrote = 0
        with open(resource_url[1], 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, leave=False, position=position) as pbar:
                pbar.set_description("  Downloading "+resource_url[1])
                pbar.update(1)
                for data in r.iter_content(1024*32):
                    wrote = wrote + len(data)
                    f.write(data)
                    pbar.update(len(data))

                pbar.write(("  Finished downloading {0}".format(resource_url[1])))

        if total_size != 0 and wrote != total_size:
            print("ERROR, something went wrong")
            if os.path.exists(resource_url[1]):
                os.remove(resource_url[1])


    # delete partially downloaded file on interrupt.
    except KeyboardInterrupt as e:
        f.close()
        print("   Removing file {0}, which has only been partially downloaded".format(resource_url[1]))
        os.remove(resource_url[1])
        raise e


if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

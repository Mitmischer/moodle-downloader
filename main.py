#!/usr/bin/python3
import mechanicalsoup
import os
from tqdm import tqdm
import math

import configparser

def main():
    conf = configparser.ConfigParser()
    conf.read("config.ini")

    if not os.path.exists("files"):
        os.mkdir("files")
        os.chdir("files")

    # login
    print("Connecting to moodle...")
    browser = mechanicalsoup.StatefulBrowser()
    browser.open("https://moodle.ruhr-uni-bochum.de/m/")
    print("Done.")
    
    print("Performing login...")
    browser.select_form('form[class="loginform"]')
    browser["username"] = conf.get("auth", "username")
    browser["password"] = conf.get("auth", "password")
    response = browser.submit_selected()

    course_urls = []
    for item in browser.get_current_page().find_all("h3", class_="coursename"):
        # the h3 only contains one anchor
        anchor = item.find_all("a")[0]
        # "defuse" the course name, such that only legal file names are obtained.
        print("Found course {0} ({1})".format(item.text.replace("/", "_"), anchor["href"]))
        course_urls.append((anchor["href"], item.text.replace("/", "_")))

    for url, coursename in course_urls:
        if not os.path.exists(coursename):
            os.mkdir(coursename)
        os.chdir(coursename)
        print(" Processing course room {}".format(coursename))
        browser.open(url)

        resource_urls = []
        # Case 1: Files are not organized
        resources =  browser.get_current_page().find_all("li", class_="resource")
        for res in resources:
            activityinstance = res.find("div", class_="activityinstance")

            res_name = activityinstance.find("span", class_="instancename").text.replace("/", "_")
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

        for resource_url in resource_urls:
            if os.path.exists(resource_url[1]):
                #print("  Skipping {}, exists already".format(resource_url[1]))
                continue

            print("  Downloading file {0}".format(resource_url[1]))
            r = browser.session.get(resource_url[0], stream=True)

            total_size = int(r.headers.get('content-length', 0))
            wrote = 0 
            with open(resource_url[1], 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True) as pbar:
                        for data in r.iter_content(1024*32):
                            wrote = wrote  + len(data)
                            f.write(data)
                            pbar.update(len(data))

            if total_size != 0 and wrote != total_size:
                print("ERROR, something went wrong")
                os.remove(resource_url[1])

        print ("  Done.")
        os.chdir("..")


if __name__=="__main__":
    main()

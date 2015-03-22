"""
HOUDINI PLAYBLAST TOOL v0.1
Date : 16 Sept 2014
Author: Rajiv Sharma
Contact Email : rajiv.vfx@gmail.com

Tutorial : http://rajivpandit.wordpress.com/2014/09/14/houdiniplayblast/

description:
============
This is Backend script for Houdini Playblast Tool.
HoudiniPlayblastTool is a small application for manage preview (Playblast) versions.
Feature of this tool :
1.Create preview and save automatically in proper location.
2.Maintain a complete list of saved playblast with version notes.
3.Version History window will display all versions.
4.Version History support multiple users.
5.from Version History You Can load any preview in a single click
6.This tool can also build movie(.mp4) if you turn on 'Build Mov'.
7.Open Recent created preview
8.Add notes to versions
9.publish previews to publish location
10. publish multiple selected previews in asset location
11. display a complete history of preview publish
12. customize paths easily
13. Send Email Notifications 
14. select after playblast tasks (play playblast, Quit Houdini, Logout system, Shutdown System)
15. choose your fav player to load previews ( MPLAY, RV Player, DJV-IMAGING)

Installation Setup:
==================
This App is design and test on Linux Operating system only.
OS Used : CentOS 7 , Ubuntu
Python : Python 2.7
copy python file in Houdini Python path folder
for Example: /home/rsharma/houdini13.0/python
Tip: add following line in houdini.env  
PYTHONPATH=/home/rsharma/houdini13.0/python

copy otl in your otl folder
for Example: /home/rsharma/houdini13.0/otls

to use 'build mov' feature you must have FFMpeg (ffmpeg version 2.2.4) install in your system

"""

import os
import shutil
import subprocess
import string
import smtplib
import getpass
import toolutils
from time import strftime
import hou


class HoudiniPlayblast(object):
    def __init__(self):
		"""
		Constructor for Houdini Playblast Class
		"""
        super(HoudiniPlayblast, self).__init__()
        self.node = hou.pwd()
        self.newVersionCheck = self.node.parm('new_version').eval()
        self.totalVersion = self.node.parm('total_version')
        self.totalPublished = self.node.parm('total_published')
        self.showByUser = self.node.parm('show_by_user')
        self.showByType = self.node.parm('show_by_type')
        self.launchPreview = self.node.parm('launch_preview')
        self.afterPbl = self.node.parm('afterplayblast')
        self.fxType = self.node.parm('fx_type').eval()
        self.emailAlert = self.node.parm('email_notification').eval()
        self.emailAddress = self.node.parm('email_address').eval()
        self.versionNote = self.node.parm('version_note').eval()
        self.guideNode = self.node.parm('display_guides').eval()
        self.buildMov = self.node.parm('build_mov').eval()
        self.incrementSave = self.node.parm('save_file').eval()
        self.customPreviewPath = self.node.parm('preview_path').evalAsString()
        self.customPublishPath = self.node.parm('publish_path').eval()
        self.filePath = str(hou.hipFile.path())
        self.path = os.path.dirname(self.filePath)
        self.sceneName = os.path.basename(self.filePath)
        self.user = getpass.getuser()
        self.initialPath = ''
        self.metaFile = ''
        self.isPublish = ''

    def previewPath(self):
        """
        This function will Return Preview path
        """
        previewBase = ''
        previewPath = ''
        fx_type = ''
        if not self.customPreviewPath:
            previewBase = self.path + "/preview/"
        else:
            previewBase = self.customPreviewPath + "/preview/"
        fx_type = self.fxType
        initial = previewBase + "%s/%s/" % (self.fxType, self.user)
        initialPath = initial + "p001" 
        if not os.path.exists(initialPath):
            previewPath = initialPath
        else:
            fxTypeID = self.showByType.evalAsInt()
            fx_type = self.showByType.menuLabels()[fxTypeID]
            userID = self.showByUser.evalAsInt()
            userInUI = self.showByUser.menuLabels()[userID]
            previewPath = previewBase + "%s/%s/" % (fx_type, userInUI)
        return previewPath, fx_type, initial

    def createPreview(self, kwargs):
        """
        this function will create preview directory before render start
        :return:
        """
        if not self.validation():
            return
        previewPath = self.previewPath()[0]
        imagePath = ''
        if not os.path.exists(previewPath):
            os.makedirs(previewPath)
            initial = self.previewPath()[2]
            self.metaFile = initial + '.mxdb'
            imagePath = self.createMetadata(previewPath)
            makePreview = self.makePreviewCommand(kwargs, imagePath)
            if makePreview:
                self.buildMovie(imagePath)
        else:
            if self.newVersionCheck:
                folderList = os.listdir(previewPath)  # Get List of all folder inside preview path
                latest = sorted(folderList)[-1]  # sort list to get latest version
                new_folder_version = int(latest.split('p')[-1]) + 1
                new_name = "p%03d" % new_folder_version
                new_folder_path = previewPath + new_name
                if not os.path.exists(new_folder_path):
                    os.makedirs(new_folder_path)
                self.metaFile = previewPath + '.mxdb'
                imagePath = self.createMetadata(new_folder_path)
                makePreview = self.makePreviewCommand(kwargs, imagePath)
                if makePreview:
                    self.buildMovie(imagePath)
            else:
                latestVersion = self.getLatestVersion()
                imagePath = self.extractInfo(latestVersion)[0]
                makePreview = self.makePreviewCommand(kwargs, imagePath)
                if makePreview:
                    self.buildMovie(imagePath)
        self.incrementalSave()
        self.updateInfo()
        self.afterPlayblast(imagePath)
        self.emailNotification(self.sceneName, imagePath)

    def createMetadata(self, path):
        """
        this function will write preview information to file
        and return the output path of image sequence
        :return:
        """
        version = path.split('/')[-1]
        x = version.split('p')[-1]
        version_number = int(x)
        fileName = hou.hscriptStringExpression('$HIPNAME')
        namewithoutframe = fileName[:-4]
        newFileName = namewithoutframe + '_%s.$F3.png' % version
        user = getpass.getuser()
        fxType = self.previewPath()[1]
        imagePath = path + '/' + newFileName
        metaInfo = "\n%s=%s=%s=%s=%s=%s" % (version, version_number, self.versionNote, user, imagePath, fxType)
        fo = open(self.metaFile, 'a')
        fo.write(metaInfo)
        fo.close()
        return imagePath

    def fetchMetadata(self):
        """
        this function will extract information from text file
        and will return a dictionary
        {version: {notes:'', user:'', path:''}}
        """
        metaFile = self.previewPath()[0] + '.mxdb'
        myDictList = []
        versionList = self.getVersionList()
        if not os.path.isfile(metaFile):
            return
        fo = open(metaFile, 'r')
        for line in fo.readlines():
            for version in versionList:
                if line.startswith(version):
                    preview_version = line.split('=')[0]
                    version_number = line.split('=')[1]
                    notes = line.split('=')[2]
                    user =line.split('=')[3]
                    path = line.split('=')[4]
                    fx_type = line.split('=')[5]
                    myDict = {version: {'preview_version': preview_version, 'version_number': version_number,'notes': notes, 'user': user, 'path': path, 'fx_type':fx_type}}
                    myDictList.append(myDict)
        return myDictList

    def updateInfo(self):
        """
        this function will update information in ui
        """
        if not os.path.exists(self.previewPath()[0]):
            self.totalVersion.lock(False)
            self.totalVersion.set(0)
            self.totalVersion.lock(True)
            return
        total_folder = self.getVersionList()
        if total_folder:
            total_number = len(total_folder)
        else:
            total_number = 0
        self.totalVersion.lock(False)
        self.totalVersion.set(total_number)
        self.totalVersion.lock(True)
        versionInfoDict = self.fetchMetadata()
        if not versionInfoDict:
            return
        for dict in versionInfoDict:
            for ver, infodata in dict.items():
                # UPDATE TOTAL VERSION
                self.totalVersion.lock(False)
                self.totalVersion.set(total_number)
                self.totalVersion.lock(True)
                # UPDATE VERSION NOTES
                ver_num = infodata['version_number']
                vper = 'version_notes_' + ver_num
                notes = infodata['notes']
                ver_notes_parm = self.node.parm(vper)
                ver_notes_parm.lock(False)
                ver_notes_parm.set(notes)
                ver_notes_parm.lock(True)

    def getVersionList(self):
        """
        this function will return list of preview folders
        :return:
        """
        versionPath = self.previewPath()[0]
        versionList = []
        if not os.path.exists(versionPath):
            return
        folderList = os.listdir(versionPath)
        sortList = sorted(folderList)
        for version in sortList:
            if not version.startswith('p'):
                pass
            elif not len(version) == 4:
                pass
            else:
                versionList.append(version)
        return versionList

    def getLatestVersion(self):
        """
        this will return the latest version
        :return:
        """
        folderList = self.getVersionList()
        if not folderList:
            return
        sortList = sorted(folderList)
        version = sortList[-1]
        x = version.split('p')[-1]
        x = int(x)
        y = x + 1
        z = y - 1
        latestVersion = str(z)
        return latestVersion

    def extractInfo(self, versionNumber):
        """
        this function will return the information related to given version
        """
        versionInfoDict = self.fetchMetadata()
        if not versionInfoDict:
            return
        for dict in versionInfoDict:
            for ver, infodata in dict.items():
                ver_num = infodata['version_number']
                if int(ver_num) == int(versionNumber):
                    preview_version = str(infodata['preview_version'])
                    preview_id = str(infodata['version_number'])
                    path = str(infodata['path']).strip()
                    note = str(infodata['notes'])
                    fx_type = str(infodata['fx_type'])
                    return path, note, preview_version, preview_id, fx_type

    def getViewport(self, viewer_or_scriptargs):
        """
        This function will return the Technical Name of Current Viewport
        Get a string representing the current viewport.
        """
        if isinstance(viewer_or_scriptargs, dict):
            activepane = toolutils.activePane(viewer_or_scriptargs)
        elif isinstance(viewer_or_scriptargs, hou.SceneViewer):
            activepane = viewer_or_scriptargs
        desktop_name = hou.ui.curDesktop().name()
        if not isinstance(activepane, hou.SceneViewer):
            raise hou.OperationFailed("Pane is not a Scene Viewer.")
        pane_name = activepane.name()
        viewport_name = activepane.curViewport().name()
        return "%s.%s.world.%s" % (desktop_name, pane_name, viewport_name)

    def makePreviewCommand(self, kwargs, imagePath):
        """
        In this function houdini preview command will excute
        """
        viewport = self.getViewport(kwargs)
        startFrame = hou.hscriptExpression('$RFSTART')
        endFrame = hou.hscriptExpression('$RFEND')
        if self.guideNode:
            hscript = "viewwrite -f %d %d -g 1.0 -q 3  %s '%s'" % (startFrame, endFrame, viewport, imagePath)
        else:
            hscript = "viewwrite -f %d %d -g 2.4 -q 3 -B %s '%s'" % (startFrame, endFrame, viewport, imagePath)
        hou.hscript(hscript)
        return 1

    def incrementalSave(self):
        """
        incremental save houdini file
        """
        if not self.incrementSave:
            return
        else:
            hou.hipFile.saveAndIncrementFileName()

    def buildMovie(self, imagePath):
        """
        this function will create movie from image sequence
        :return:
        """
        if not self.buildMov:
            return
        inputPath = imagePath.replace('$F3', '%03d')
        inputFile = os.path.basename(inputPath)
        outputFile = hou.hscriptStringExpression('$HIPNAME').split('.')[0] + '.mp4'
        outputPath = os.path.dirname(inputPath)
        command = 'cd %s\nffmpeg -y -r 24 -i "%s"  "%s"' % (outputPath, inputFile, outputFile)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdoutdata, error = process.communicate()

    def afterPlayblast(self, imagePath):
        """
        action perform after playblast
        """
        postID = self.afterPbl.evalAsInt()
        postTask = self.afterPbl.menuLabels()[postID]
        if postTask == 'Play Playblast':
            self.showAfterPlayblast(imagePath)
        if postTask == 'Quit Houdini':
            hou.exit(suppress_save_prompt=True)
        if postTask == 'Log Out System':
            os.system('gnome-session-quit --force')
        if postTask == 'Shutdown System':
            os.system('shutdown -h now')

    def emailNotification(self, sceneName, imagePath):
        """
        this function will send email alert
        """
        if not self.emailAlert:
            return
        if self.emailAddress:
            if not '@' in self.emailAddress:
                hou.ui.displayMessage('Invalid Email Address')
                return
            if not '.com' in self.emailAddress:
                hou.ui.displayMessage('Invalid Email Address')
                return
            datetime = strftime("%a, %d %b %Y %H:%M:%S")
            SMTPserver = "localhost"
            # To is a comma-separated list
            To = self.emailAddress
            From = "houdiniplayblast"
            Subj = "Houdini Playblast : %s " % sceneName
            Text = """Hello %s.
            Houdini Playblast of %s is done

            Completion Date and Time : %s

            Playblast Location : %s .""" % (self.user, sceneName, datetime, imagePath)

            Body = string.join((
                "From: %s" % From,
                "To: %s" % To,
                "Subject: %s" % Subj,
                "",
                Text,
                 ), "\r\n")
            s = smtplib.SMTP(SMTPserver)
            s.sendmail(From, [To], Body)
            s.quit()

    def showPreview(self, versionNumber):
        """
        execute mplay command with path
        """
        imagePath = ''
        if not self.isPublish:
            print 'showPreview=versionNumber', versionNumber
            imagePath = self.extractInfo(versionNumber)[0]
            print 'showPreview=imagePath', imagePath
        else:
            imagePath = self.getPublishPreviewPath(versionNumber)
        self.showCommand(imagePath)

    def showCommand(self, imagePath):
        """
        this function contain show commands
        """
        playerID = self.launchPreview.evalAsInt()
        player = self.launchPreview.menuLabels()[playerID]
        if imagePath:
            command = ''
            path = imagePath
            if player == 'Mplay':
                command = "mplay '%s'" % path
            if player == 'RV Player':
                images_location = os.path.dirname(path)
                command = "rv '%s'" % images_location
            if player == 'DJV Imaging Player':
                command = "djv_view '%s'" % path
            os.system(command)
        else:
            hou.ui.displayMessage('No Preview Found')

    def showLastPreview(self):
        """
        this function will execute last preview
        :return:
        """
        if not os.path.exists(self.previewPath()[0]):
            return
        latestVersion = self.getLatestVersion()
        print 'latestVersion', latestVersion
        self.showPreview(latestVersion)

    def showAfterPlayblast(self, imagePath):
        """
        show after Playblast function
        """
        if not os.path.exists(self.previewPath()[0]):
            return
        self.showCommand(imagePath)

    def showSelectedPreview(self, scriptargs):
        """
        this function will execute selected preview
        :return:
        """
        show_button = "{0}".format(scriptargs["parm"].name())
        show_button = str(show_button)
        button_num = show_button.split('_')[-1]
        self.showPreview(button_num)

    def showSelectedPublishPreview(self, scriptargs):
        """
        this function will execute selected preview
        :return:
        """
        self.isPublish = 'True'
        show_button = "{0}".format(scriptargs["parm"].name())
        show_button = str(show_button)
        button_num = show_button.split('_')[-1]
        self.showPreview(button_num)

    def validation(self):
        """
        this function will check the file path
        and return with warning if file name is wrong
        if file in not in production folder
        """
        return 1

    def publishPath(self):
        """
        this function will return publish path.
        """
        if not self.customPublishPath:
            publishLocation = self.path + '/publish/'
            return publishLocation
        else:
            if not os.path.exists(self.customPublishPath):
                hou.ui.displayMessage('Invalid Publish Path')
            else:
                publishLocation = self.customPublishPath + '/publish/'
                return publishLocation

    def publishInit(self, version_number):
        """
        this function will initilize publish metadata
        """
        if not os.path.exists(self.previewPath()[0]):
            return
        publishLocation = self.publishPath()
        imagePath = self.extractInfo(version_number)[0]
        fx_type = str(self.extractInfo(version_number)[4]).rstrip()
        source = os.path.dirname(imagePath)  # SOURCE
        if not os.path.exists(publishLocation):
            os.makedirs(publishLocation)
        publishList = os.listdir(publishLocation)
        if not publishList:
            publishVersion = 'v001'
        else:
            latest = sorted(publishList)[-1]
            new_folder_version = int(latest.split('v')[-1]) + 1
            publishVersion = "v%03d" % new_folder_version
        destination = publishLocation + publishVersion  # DESTINATION
        self.publishTranfer(source, destination)
        # CREATE PUBLISH METADATA
        publishMetadataFile = publishLocation + '.mxdb'
        preview_path = self.extractInfo(version_number)[0]
        preview_note = self.extractInfo(version_number)[1]
        preview_version = self.extractInfo(version_number)[2]
        preview_id = self.extractInfo(version_number)[3]
        publish_version = publishVersion
        fileName = imagePath.split('/')[-1]
        publish_path = destination + '/' + fileName
        user = getpass.getuser()
        datetime = strftime("%a, %d %b %Y %H:%M:%S")
        publish_info = '\n%s=%s=%s=%s=%s=%s=%s=%s=%s' %(publish_version,
                                                   preview_path,
                                                   preview_id,
                                                   preview_note,
                                                   preview_version,
                                                   publish_path,
                                                   user,
                                                   datetime,
                                                   fx_type
                                                    )
        fo = open(publishMetadataFile, 'a')
        fo.write(publish_info)
        fo.close()
        self.updatePublishInfo()

    def publishTranfer(self, source, destination):
        """
        Publish Preview in publish Location
        """
        if not os.path.exists(destination):
            os.makedirs(destination)
        list = os.listdir(source)
        for files in sorted(list):
            src_file_path = source + '/' + files
            dst_file_path = destination + '/' + files
            try:
                shutil.copyfile(src_file_path, dst_file_path)
            except IOError:
                print src_file_path + " does not exist"
        hou.ui.displayMessage('Preview Published Successfully')

    def publishLastPreview(self):
        """
        this function will publish last preview
        """
        if self.getLatestPublishVersion():
            self.publishInit(self.getLatestPublishVersion())
        else:
            self.publishInit(1)

    def publishSelectedPreview(self):
        """
        this function will Publish selected preview
        :return:
        """
        total = self.totalVersion.evalAsInt()
        count = 1
        for e in range(total):
            x = e + count
            ver_chk_name = 'ver_%s' % x
            verCheckNode = self.node.parm(ver_chk_name).evalAsInt()
            if verCheckNode:
                self.publishInit(x)

    def getPublishVersionList(self):
        """
        this function will return list of preview folders
        :return:
        """
        versionPath = self.publishPath()
        versionList = []
        if not os.path.exists(versionPath):
            return
        folderList = os.listdir(versionPath)
        sortList = sorted(folderList)
        for version in sortList:
            if not version.startswith('v'):
                pass
            elif not len(version) == 4:
                pass
            else:
                versionList.append(version)
        return versionList

    def getLatestPublishVersion(self):
        """
        this will return the latest version
        :return:
        """
        folderList = self.getPublishVersionList()
        if not folderList:
            return
        sortList = sorted(folderList)
        version = sortList[-1]
        x = version.split('v')[-1]
        x = int(x)
        y = x + 1
        z = y - 1
        latestVersion = str(z)
        return latestVersion

    def getPublishPreviewPath(self, version):
        """
        This function will return publish preview path
        """
        clickedVersion = "v%03d" % int(version)
        metadata = self.publishPath() + '.mxdb'
        if os.path.isfile(metadata):
            fileOpen = open(metadata, 'r')
            for line in fileOpen.readlines():
                if line.startswith(clickedVersion):
                    publish_version = line.split('=')[0]
                    preview_path = line.split('=')[1]
                    preview_id = line.split('=')[2]
                    preview_note =line.split('=')[3]
                    preview_version = line.split('=')[4]
                    publish_path = line.split('=')[5]
                    user =line.split('=')[6]
                    datetime = line.split('=')[7]
                    fx_type = line.split('=')[8]
                    return publish_path


    def updatePublishInfo(self):
        """
        this function will populate publish ui
        """
        metadata = self.publishPath() + '.mxdb'
        versionList = self.getPublishVersionList()
        if versionList:
            total = len(self.getPublishVersionList())
            self.totalPublished.lock(False)
            self.totalPublished.set(total)
            self.totalPublished.lock(True)
        if os.path.isfile(metadata):
            fileOpen = open(metadata, 'r')
            for line in fileOpen.readlines():
                for version in versionList:
                    if line.startswith(version):
                        publish_version = line.split('=')[0]
                        preview_path = line.split('=')[1]
                        preview_id = line.split('=')[2]
                        preview_note =line.split('=')[3]
                        preview_version = line.split('=')[4]
                        publish_path = line.split('=')[5]
                        user =line.split('=')[6]
                        datetime = line.split('=')[7]
                        fx_type = line.split('=')[8]
                        publishInfo = '%s of %s by %s on %s' % (preview_version, fx_type, user, datetime)
                        x = publish_version.split('v')[-1]
                        x = int(x)
                        y = x + 1
                        version = y - 1
                        pubNodeName = 'pub_note_%s' % version
                        pubNode = self.node.parm(pubNodeName)
                        pubNode.lock(False)
                        pubNode.set(publishInfo)
                        pubNode.lock(True)
        else:
            self.totalPublished.lock(False)
            self.totalPublished.set(0)
            self.totalPublished.lock(True)



from qgis.core import *
from qgis.PyQt.QtCore import QUrl,  Qt
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtNetwork import QNetworkRequest, QNetworkReply
from .srtm_downloader_login import Login
import os
      
class Download:

    def __init__(self,  parent=None,  iface=None):    
        self.parent = parent
        self.iface = iface     
        self.login_accepted = False
        self.username = None
        self.password = None
        self.akt_download = 0
        self.all_download = 0
        self.request_is_aborted = False
        self.nam = QgsNetworkAccessManager()
        self.nam.authenticationRequired.connect(self.set_credentials)
        self.nam.finished.connect(self.reply_finished)           
        self.login = Login()  
            
    def layer_exists(self,  name):            
        
        if len(QgsProject.instance().mapLayersByName(name)) != 0:
            return True
        else:
            return False
        

    def get_image(self,  url,  filename,  lat_tx,  lon_tx, load_to_canvas=True):
        layer_name = "%s%s.hgt" % (lat_tx,  lon_tx)

        if not self.layer_exists(layer_name):
            self.filename = filename 
            self.load_to_canvas = True       
            download_url = QUrl(url)    
            req = QNetworkRequest(download_url)
            self.nam.get(req)  
            
    def set_credentials(self, reply, authenticator):
        
        if not  self.request_is_aborted:
            if self.login.exec_():        
                self.authenticator = authenticator
                self.authenticator.setUser(self.login.username)
                self.authenticator.setPassword(self.login.password)     
            else:
                reply.abort()
                self.request_is_aborted = True
                self.parent.download_finished(show_message=False,  abort=True)
     
    def reply_finished(self, reply):    
        
        if reply != None:
            possibleRedirectUrl = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
            
        # If the URL is not empty, we're being redirected. 
            if possibleRedirectUrl != None:
                request = QNetworkRequest(possibleRedirectUrl)
                result = self.nam.get(request)  
                result.downloadProgress.connect(self.progress)
            else:             
                if reply.error() != None:
                    if reply.error() ==  QNetworkReply.ContentNotFoundError:
                        self.parent.set_progress()
                        reply.abort()
                        reply.deleteLater()
                        
                    elif reply.error() ==  QNetworkReply.NoError:
#                        QApplication.setOverrideCursor(Qt.WaitCursor)
                        result = reply.readAll()
                        f = open(self.filename, 'wb')
                        f.write(result)
                        f.close()      
                        
                        
                        out_image = self.unzip(self.filename)
                        (dir, file) = os.path.split(out_image)
                        if not self.layer_exists(file):
                            self.iface.addRasterLayer(out_image, file)
                        
                        self.parent.set_progress()  
                            
                    # Clean up. */
                        reply.deleteLater()
                    
    def progress(self,  min,  max):
        self.akt_download += min
        self.all_download += max
        self.parent.lbl_progress_values.setText('Downloading %s' % (self.akt_download))        
        
    def unzip(self,  zip_file):
        import zipfile
        (dir, file) = os.path.split(zip_file)

        if not dir.endswith(':') and not os.path.exists(dir):
            os.mkdir(dir)
        
        try:
            zf = zipfile.ZipFile(zip_file)
    
            # extract files to directory structure
            for i, name in enumerate(zf.namelist()):
                if not name.endswith('/'):
                    outfile = open(os.path.join(dir, name), 'wb')
                    outfile.write(zf.read(name))
                    outfile.flush()
                    outfile.close()
                    return os.path.join(dir, name)
        except:
            return None


    def _makedirs(self, directories, basedir):
        """ Create any directories that don't currently exist """
        for dir in directories:
            curdir = os.path.join(basedir, dir)
            if not os.path.exists(curdir):
                os.mkdir(curdir)           


    def _listdirs(self, file):
        """ Grabs all the directories in the zip structure
        This is necessary to create the structure before trying
        to extract the file to it. """
        zf = zipfile.ZipFile(file)

        dirs = []

        for name in zf.namelist():
            if name.endswith('/'):
                dirs.append(name)

        dirs.sort()
        return dirs                
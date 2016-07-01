import sys, time, pycurl, urllib
import numpy as np
import matplotlib.pyplot as plt

class urlObserver(object):
    rtt = []
    goodPut = []
    csrfToken = None
    
    def __init__(self, url_LOGIN, url_POST,url_ROOT, credentials, cookies = "",rep_RATE = 30, review = True):
        self.url_LOGIN = url_LOGIN
        self.url_POST = url_POST
        self.url_ROOT = url_ROOT
        self.creds = credentials
        
        #cookies may be filed by passing a file name ie "cookie.txt"
        self.cookie_file = cookies
        #network probe repitition rate may be increased for testing
        self.rep_RATE = rep_RATE
        #review probe data upon program completion
        self.review = review
        
        #curl object
        self.c = pycurl.Curl()
    
    """Helper functions"""
    def _avg(self,data):
        return np.average(data)
    
    def _reviewData(self):
        #check data has appended to arrays to prevent division by zero problems
        if len(self.rtt) != 0 and len(self.goodPut) != 0:
            thistitle = "Review Network Data"
            fig = plt.figure(thistitle)
            
            plt.subplot(1,2,1)
            plt.plot(self.rtt,linewidth=2.0)
            plt.hold()
            #plot average line
            plt.axhline(y=self._avg(self.rtt), xmin=0, xmax=len(self.rtt), color = 'r')
            plt.title("Round Trip Times")
            
            plt.subplot(1,2,2)
            plt.plot(self.goodPut,linewidth=2.0)
            plt.hold()
            #plot average line
            plt.axhline(y=self._avg(self.goodPut), xmin=0, xmax=len(self.goodPut), color = 'r')
            plt.title("Good Put Data")
            
            plt.show()
            
    """Network functions"""
    def _login(self, verbose = False):
        
        #set values to prepare for login attempt
        try:
            # A string with the name and path of an appropriate file
            cookie_file_name = "cookies.txt"
            
            #set pycurl options
            self.c.setopt(pycurl.FOLLOWLOCATION, 1)
            self.c.setopt(self.c.CONNECTTIMEOUT, 5)
            self.c.setopt(self.c.TIMEOUT, 8)
            self.c.setopt(self.c.COOKIEJAR, cookie_file_name)
            self.c.setopt(pycurl.COOKIEFILE, cookie_file_name)
            self.c.setopt(self.c.URL, self.url_LOGIN)
            self.c.setopt(self.c.VERBOSE, verbose)
            self.c.setopt(self.c.POSTREDIR, pycurl.REDIR_POST_ALL)
            self.c.setopt(pycurl.WRITEFUNCTION, lambda arg: None)
            self.c.setopt(self.c.FAILONERROR, True)
            
            try:
                #collect cookie
                self.c.perform()
                cookies =  self.c.getinfo(pycurl.INFO_COOKIELIST)
                
                #search through cookies for csrf_token
                for cookie in cookies:
                    cookieArray = cookie.split("\t")
                    for i in range(len(cookieArray)):
                        if cookieArray[i] == 'csrftoken':
                            self.csrfToken = cookieArray[i+1]
                            print "Found authentication token : " + str(self.csrfToken)

                #return if no csrfToken is found
                if self.csrfToken is None:
                    print "Error: no csrfToken found"
                    return False

                #add token to login details and encode for post
                self.creds['csrfmiddlewaretoken'] = self.csrfToken
                login = urllib.urlencode(self.creds)
                self.c.setopt(pycurl.HTTPHEADER, ['X-CSRF-Token: ' + str(self.csrfToken)]);
                
                #post should be directed to 'POST /login/ajax/ HTTP/1.1', as per the html header retrieve on login
                self.c.setopt(pycurl.URL, self.url_POST)
                self.c.setopt(pycurl.POST,1)
                self.c.setopt(self.c.POSTFIELDS, login)
                self.c.perform()
                
                #set cookies to enter into root and perform _get on site to finalize login
                self.c.setopt(pycurl.POST,0)
                self.c.setopt(pycurl.COOKIE, "_next_=root")
                self.c.setopt(pycurl.URL,self.url_ROOT)
                self.c.perform()
            
            #catch errors and output to user
            except pycurl.error, error:
                errno, errstr = error
                print 'A pycurl error occurred: ', errstr
                return False
            
            #in the absence of thrown errors return True to continue program
            return True
        
        #exit on user input, cease program
        except KeyboardInterrupt:
            return False
            
    def _networkProbe(self):
        
        #attempt login, if exit without error perform probe
        if self._login():
            
            #stdout welcome prompt to user following login
            print "\nProbing network\nPress Crtl + C to exit and review data\n"
            print "Samples\t |Last RTT (s)\t |Last GoodPut (bit/s)"
            
            i = 0
            while True:
                try:
                    #capture timestamp for accurate sleep length
                    starttime = time.time()
                    
                    i=i+1
                    #set and perform request
                    self.c.setopt(self.c.URL, self.url_ROOT)
                    self.c.perform()
                    
                    #retrieve and store rtt and goodPut (note prompt requests goodPut in BIT/S)
                    t = self.c.getinfo(self.c.TOTAL_TIME) - self.c.getinfo(self.c.PRETRANSFER_TIME)
                    self.rtt.append(t)
                    
                    d_BIT = self.c.getinfo(self.c.SIZE_DOWNLOAD)*8.0/t
                    self.goodPut.append(d_BIT)
                    
                    #stdout view for user
                    sys.stdout.flush()
                    print  str(i)+"\t |"+str("{0:.3f}".format(t))+"\t\t |"+\
                    str("{0:.3f}".format(d_BIT)), "\r",
                    
                    #sleep for remaining duration of rep_RATE
                    time.sleep(self.rep_RATE -((time.time() - starttime) % self.rep_RATE))
                    
                #escape on user input
                except KeyboardInterrupt:
                    break
                    
                #escape of pycurl error
                except pycurl.error, error:
                    errno, errstr = error
                    print 'A pycurl error occurred: ', errstr
                    break 
            
            #output final averages to user
            print "\n\nFinal Averages"
            print "RTT\t : ", str("{0:.5f}".format(self._avg(self.rtt)))
            print "GoodPut\t : ", str("{0:.5f}".format(self._avg(self.goodPut)))
            
            if self.review:
                self._reviewData()
        else:
            print "Unsuccessful network access attempt.\nExiting..."
        
        #ensure connection is closed
        self.c.close()

if __name__ == "__main__":
    #set login target, post address, and root domain for network analysis
    url_TARGET = "http://authenticationtest.herokuapp.com/login/"
    url_POST = "https://authenticationtest.herokuapp.com/login/ajax/"
    url_ROOT = "https://authenticationtest.herokuapp.com/"
    
    #seed credentials
    usr = 'testuser'
    pw = '54321password12345'
    credentials = {'username': usr, 'password':pw}
    
    #instance nework connection and test network
    connection = urlObserver(url_TARGET,url_POST, url_ROOT,credentials)
    connection._networkProbe()
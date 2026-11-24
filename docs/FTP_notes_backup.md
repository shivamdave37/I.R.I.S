FTP Enumeration

Part 1 — FTP kya hai?
FTP ka full form hai File Transfer Protocol.

FTP ek network protocol hai jiska use client aur server ke beech files transfer karne ke liye kiya jata hai.

Real-life example samjho:
- Tumhare paas ek computer hai — ye client hai.
- Dusre computer par files stored hain — ye server hai.
- Tum client se server par file upload ya server se download karte ho — ye FTP ka use case hai


FTP Client — Kali Linux
Request / Login / Download

Network connection
FTP Server — Ubuntu
Authentication / Files / Directories


FTP kahan use hota hai?
- Company ke internal servers par file exchange.
- Website deployment ke kuch legacy workflows.
- Internal file-transfer systems.
- Lab environments mein protocol aur server configuration seekhne ke liye.

###
FTP ports aur connection
Port	Kaam
TCP 21	FTP control connection — commands aur responses
TCP 20	Traditional active FTP mein data connection ka source port
Passive-mode ports	Server ki configured range ke according data connection

Important concept: Port 21 open hone ka matlab ye nahi ki port 20 bhi open hona chahiye. Passive FTP mein data connection alag configured port range use kar sakta hai.


Active vs Passive FTP
- Active FTP: Client control connection banata hai aur server data connection initiate karta hai.
- Passive FTP: Client control aur data connections dono initiate karta hai. NAT aur firewalls ke peeche ye aksar easier hota hai, lekin server par passive port range configure karni padti hai.


Part 3 — FTP vs FTPS vs SFTP
Protocol	Security	Connection
FTP	Default FTP mein credentials/data encrypted nahi hote	FTP service
FTPS	TLS encryption add karta hai	FTP + TLS
SFTP	SSH ke through encrypted file transfer	SSH service, commonly TCP 22

#SFTP aur FTPS same protocol nahi hain. SFTP, SSH ka part hai; FTPS, FTP ko TLS ke saath secure karta hai.


##Practical lab setup

Lab network
Kali Linux

Client / Scanner

Example: 192.168.56.10

Ubuntu

FTP Server

Example: 192.168.56.20


Ye example IPs hain, actual IPs nahi. Apne VM ke IPs use karna. VirtualBox mein dono VMs ko same Host-only network par rakhna; lab ko public network par expose mat karna.


##############
Step 1 — Ubuntu ka IP address check karo
Ubuntu terminal par:
ip -br addr


Possible output:
lo               UNKNOWN        127.0.0.1/8
enp0s3           UP             192.168.56.20/24


Meaning:
- lo — local loopback interface.
- enp0s3 — network interface ka naam; tumhare system par different ho sakta hai.
- 192.168.56.20/24 — example IP aur subnet.
Ab Kali Linux par bhi same command run karo aur dono machines ki connectivity verify karo:
ping -c 4 192.168.56.20


Example target IP ko apne Ubuntu IP se replace karna.

Expected result: Replies mil sakte hain. Agar ping fail ho, to zaroori nahi ki FTP bhi fail hoga—firewall ICMP ko block kar sakta hai. Dono VMs ka network configuration verify karo.


#########
Step 2 — Ubuntu par FTP server install karo
Ubuntu terminal mein:
sudo apt update


Package lists update hongi.
sudo apt install vsftpd ftp -y


- vsftpd — FTP server.
- ftp — command-line FTP client, agar distribution ke repositories mein available ho.
- -y — installation confirmation automatically accept karta hai.
Server version check karo:
vsftpd -v


Service start aur enable karo:
sudo systemctl enable --now vsftpd


Status check:
sudo systemctl status vsftpd


Expected status mein ye dikhna chahiye:
Active: active (running)


Agar service start nahi hoti, error details dekho:
sudo journalctl -u vsftpd -n 50 --no-pager


Is command se service ke recent logs milenge.


##############
Step 3 — FTP server ko safe lab configuration do
Pehle existing configuration ka backup banao:
sudo cp /etc/vsftpd.conf /etc/vsftpd.conf.backup


Configuration file kholo:
sudo nano /etc/vsftpd.conf


Existing settings ko dhyan se check karo. Neeche di gayi settings ko ensure karo ki active hon aur duplicate conflicting entries na hon:
anonymous_enable=NO
local_enable=YES
write_enable=NO


Inka meaning:
- anonymous_enable=NO — anonymous login disable.
- local_enable=YES — local Ubuntu users ko FTP login allow.
- write_enable=NO — FTP se file upload ya write operations disable.
File save karne ke liye Nano mein Ctrl + O, Enter, phir Ctrl + X press karo.

Service restart karo:
sudo systemctl restart vsftpd
sudo systemctl status vsftpd


Security note: Normal FTP credentials encrypted nahi hote. Is lab ko private network tak hi limit rakho; real accounts ya real passwords use mat karna. Production mein secure transfer ke liye SFTP ya correctly configured FTPS prefer karo.

#############
Step 4 — Test ke liye ek dedicated FTP user banao
Ubuntu par:
sudo adduser labftp


Terminal password maangega. Sirf lab ke liye temporary password set karo; ise real account par reuse mat karna.

Test file banao:
sudo mkdir -p /srv/ftp-lab
echo "FTP Enumeration Practice Lab" | sudo tee /srv/ftp-lab/readme.txt


Ab FTP user ke home directory mein test file rakhne ke liye:
sudo mkdir -p /home/labftp/ftp-files
sudo cp /srv/ftp-lab/readme.txt /home/labftp/ftp-files/
sudo chown -R labftp:labftp /home/labftp/ftp-files
sudo chmod 755 /home/labftp/ftp-files
sudo chmod 644 /home/labftp/ftp-files/readme.txt


Is tarah dedicated test directory mein readable file hogi, aur hum unnecessary server directories expose nahi karenge.


######
Part 5 — Kali Linux se FTP Enumeration
Ab Kali par wapas aao. Neeche 192.168.56.20 ko apne actual Ubuntu IP se replace karna.
Step 5 — Port discovery with Nmap
nmap -p 21 192.168.56.20


Meaning:
- nmap — network discovery aur service assessment tool.
- -p 21 — sirf TCP port 21 check karo.
- IP — tumhari authorized lab target machine.
Possible output:
PORT   STATE SERVICE
21/tcp open  ftp


Interpretation:
- open — port par service connection accept kar rahi hai.
- closed — target reachable hai, lekin port par service listen nahi kar rahi.
- filtered — firewall ya network filtering ki wajah se Nmap state determine nahi kar saka.
Yaad rakhna: open ka matlab vulnerable nahi hota.

####
Step 6 — Service/version detection
nmap -sV -p 21 192.168.56.20


-sV service detection attempt karta hai. Output mein FTP service ka naam aur kabhi version dikh sakta hai.

Example:
PORT   STATE SERVICE VERSION
21/tcp open  ftp     vsftpd ...


Version detection exact version hamesha identify nahi kar pata. Aur version milne ka matlab ye bhi nahi ki vulnerability confirmed hai.


###
Step 7 — FTP banner check
Kali par FTP client available ho to:
ftp 192.168.56.20


Server welcome message ya login prompt de sakta hai. Output kuch aisa ho sakta hai:
Connected to 192.168.56.20.
220 (vsFTPd ...)
Name (192.168.56.20:...):


220 FTP server ka greeting/status response hai. Banner se product ka clue mil sakta hai, lekin banner ko final proof of exact version mat samajhna.

Login prompt par apne lab user ka naam enter karo:
Name: labftp
Password: [lab password]


Password type karte waqt terminal par characters na dikhna normal hai.

Login successful ho to:
230 Login successful.


Ab commands:
pwd
ls
cd ftp-files
ls
get readme.txt
bye


Inka meaning:
- pwd — current remote directory.
- ls — remote directory listing.
- cd ftp-files — remote directory change.
- get readme.txt — test file download.
- bye — FTP session end.
Downloaded file check karne ke liye:
cat readme.txt


Expected content:
FTP Enumeration Practice Lab


Agar ftp command missing hai, Ubuntu par FTP server phir bhi chal sakta hai; Kali par client install karo:
sudo apt update
sudo apt install ftp -y


Agar package available na ho, curl se bhi service behavior test kar sakte ho.


#Part 6 — Anonymous FTP access check

###FTP Enumeration ka important security check hai.


Anonymous access ka matlab server special guest-style login allow karta hai, bina normal personal account ke. Kuch public file repositories mein ye intentional hota hai; har case mein vulnerability nahi.

Kali par apne lab target ke against run karo:
curl -v --max-time 5 \
  --user 'anonymous:anonymous@example.com' \
  ftp://192.168.56.20/


192.168.56.20 ko actual lab IP se replace karna.

Command ke parts:
- curl — server se communicate karne wala client.
- -v — connection details aur protocol responses dikhata hai.
- --max-time 5 — command ko 5 seconds ke baad timeout karta hai.
- --user — FTP login credentials provide karta hai.
- ftp://.../ — FTP server ki root listing request karta hai.
Hamari lab configuration mein anonymous access disabled hai, isliye expected result authentication failure ho sakta hai, jaise:
530 This FTP server is anonymous only ...


Ya server ka koi doosra 530 response aa sakta hai. Exact message software aur configuration par depend karta hai. Agar 530 aaye, to uska matlab login reject hua; response akela rejection ka exact reason prove nahi karta.

Agar server anonymous access allow karta hai, to check karo ki kaunsi files readable hain aur kya write access bhi available hai. Bina authorization upload, delete ya modify test mat karna.



###
Part 7 — FTP Enumeration ka complete workflow
1. Identify target — lab VM ka actual IP note karo.
2. Discover port — Nmap se TCP 21 check karo.
3. Identify service — nmap -sV se FTP service information collect karo.
4. Check authentication — dedicated lab user se login verify karo.
5. Inspect permitted files — directories aur sample file ki accessibility check karo.
6. Check anonymous access — guest login allowed hai ya reject hota hai, evidence note karo.
7. Document findings — observations, evidence, risk aur remediation likho.


###
art 8 — Troubleshooting
Problem	Kya check karna hai
Port 21 closed	sudo systemctl status vsftpd
Port filtered	VM network aur firewall rules
Connection refused	Server service aur target IP
530 Login incorrect	Username, password aur local-user configuration
Login successful, ls fail	Permissions, directory access aur FTP logs
ftp: command not found	Kali par FTP client install karo
Connection timed out	Network reachability, routing aur firewall

Ubuntu par FTP logs check karne ke liye:
sudo journalctl -u vsftpd -n 50 --no-pager


Agar tumne galti se config file change kar di aur server start nahi ho raha, backup restore kar sakte ho:
sudo cp /etc/vsftpd.conf.backup /etc/vsftpd.conf
sudo systemctl restart vsftpd


Dhyan rahe: backup restore karne se lab ki baad mein ki gayi configuration changes bhi undo ho jayengi.


Part 9 — Security Findings aur Remediation

| Finding                              | Assessment                                      | Recommended Action                                                   |
|--------------------------------------|-------------------------------------------------|----------------------------------------------------------------------|
| FTP port exposed                     | Exposure observed; risk context-dependent       | Access ko trusted networks tak restrict karo.                        |
| Anonymous listing allowed            | Public files expose ho sakti hain               | Business need na ho to anonymous access disable karo.               |
| FTP credentials plaintext mein       | Credentials interception ka risk                | SFTP ya properly configured FTPS use karo.                           |
| transmit hote hain                   |                                                 |                                                                      |
| Unnecessary files readable hain      | Information disclosure ho sakta hai             | Least-privilege permissions lagao.                                   |
| Outdated server version              | Potential patching concern                       | Version verify karke supported release aur security updates apply   |
|                                      |                                                 | karo.    

                                                            |

Professional rule: Jo cheez tumne actually test nahi ki, usko confirmed vulnerability report mat karna. Har finding ke saath evidence aur limitation likho.


#Part 10 practical assignment
Practical checklist

0/8 complete



[ ] Ubuntu lab par vsftpd install aur service start karo.
[ ] Kali aur Ubuntu ke actual IP addresses note karo.
[ ] Nmap se TCP port 21 ka state record karo.
[ ] FTP service detection ka output save karo.
[ ] Dedicated lab user se login aur permitted directory listing test karo.
[ ] Test file download karke content verify karo.
[ ] Anonymous access ka result record karo.
[ ] Findings aur remediation ke saath report complete karo.

##
Part 11 — Report template
# FTP Enumeration Lab Report

**Student Name:**  
**Date:**  
**Lab Target IP:**  
**Testing Scope:** Authorized private lab only

## 1. Objective
To identify the FTP service, inspect authentication behavior and document accessible resources.

## 2. Tools Used
- Kali Linux
- Nmap
- FTP client / curl
- Ubuntu Server with vsftpd

## 3. Evidence and Observations
- TCP 21 state:
- Detected service/version:
- Authenticated login result:
- Accessible directories:
- Test file download result:
- Anonymous access result:
- Relevant command output / screenshots:

## 4. Findings
For each finding, record the evidence, impact, risk level and limitations.

## 5. Recommendations
- Disable unnecessary anonymous access.
- Restrict FTP access to trusted networks.
- Use SFTP or properly configured FTPS for secure transfer.
- Apply least-privilege file permissions.
- Keep the server updated.

## 6. Conclusion
Summarize what was verified, what was not tested and the recommended next steps.

#!/usr/bin/python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------
#    This file is part of WAPT
#    Copyright (C) 2013  Tranquil IT Systems http://www.tranquil.it
#    WAPT aims to help Windows systems administrators to deploy
#    setup and update applications on users PC.
#
#    WAPT is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    WAPT is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with WAPT.  If not, see <http://www.gnu.org/licenses/>.
#
# -----------------------------------------------------------------------
from __future__ import absolute_import
import os
import socket
import struct
import getpass
import platform
import configparser
import platform
import psutil
import netifaces
import json
import cpuinfo
import sys
import subprocess
import logging
import glob
import plistlib
import datetime
import platform
from waptutils import (ensure_unicode, makepath, ensure_dir,currentdate,currentdatetime,_lower,ini2winstr,error,get_main_ip)

try:
    import apt
except:
    apt=None

try:
    import rpm
except:
    rpm=None


logger = logging.getLogger()


def local_drives():
    partitions = psutil.disk_partitions()
    result = {}
    for elem in partitions:
        result[elem.mountpoint]=dict(elem._asdict())
        result[elem.mountpoint]=result[elem.mountpoint].update(dict(psutil.disk_usage(elem.mountpoint)._asdict()))
    return result

def host_metrics():
    """Frequently updated host data
    """
    result = {}
    # volatile...
    result['physical_memory'] = psutil.virtual_memory().total
    result['virtual_memory'] = psutil.swap_memory().total
    result['local_drives'] = local_drives()
    result['logged_in_users'] = get_loggedinusers()
    result['last_logged_on_user'] = get_last_logged_on_user()

    # memory usage
    current_process = psutil.Process()
    result['wapt-memory-usage'] = dir(current_process.memory_info())

    return result


def default_gateway():
    """Returns default ipv4 current gateway"""
    gateways = netifaces.gateways()
    if gateways:
        default_gw = gateways.get('default',None)
        if default_gw:
            default_inet_gw = default_gw.get(netifaces.AF_INET,None)
        else:
            default_inet_gw = None
    if default_gateway:
        return default_inet_gw[0]
    else:
        return None


def networking():
    """return a list of (iface,mac,{addr,broadcast,netmask})
    """
    ifaces = netifaces.interfaces()
    local_ips = socket.gethostbyname_ex(socket.gethostname())[2]

    res = []
    for i in ifaces:
        params = netifaces.ifaddresses(i)
        if netifaces.AF_LINK in params and params[netifaces.AF_LINK][0]['addr'] and not params[netifaces.AF_LINK][0]['addr'].startswith('00:00:00'):
            iface = {'iface':i,'mac':params
            [netifaces.AF_LINK][0]['addr']}
            if netifaces.AF_INET in params:
                iface.update(params[netifaces.AF_INET][0])
                iface['connected'] = 'addr' in iface and iface['addr'] in local_ips
            res.append( iface )
    return res



def get_default_gateways():
    if sys.platform.startswith('linux'):
        """Read the default gateway directly from /proc."""
        with open("/proc/net/route") as fh:
            for line in fh:
                fields = line.strip().split()
                if fields[1] != '00000000' or not int(fields[3], 16) & 2:
                    continue
                return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    else:
        #TODO: Darwin
        pass

def user_local_appdata():
    r"""Return the local appdata profile of current user

    Returns:
        str: path like u'C:\\Users\\user\\AppData\\Local'
    """
    return ensure_unicode(makepath(os.environ['HOME'],'.config'))

def isLinux64():
    return platform.machine().endswith('64')

def get_current_user():
    r"""Get the login name for the current user.
    >>> get_current_user()
    u'htouvet'
    """
    return ensure_unicode(getpass.getuser())

def get_distrib_version():
    return platform.linux_distribution()[1]

def get_distrib_linux():
    return platform.linux_distribution()[0]

def get_kernel_version():
    return os.uname()[2]

def get_domain_batch():
    """Return main DNS domain of the computer

    Returns:
        str: domain name

    >>> get_domain_batch()
    u'tranquilit.local'
    """

    try:
        return socket.getfqdn().split('.', 1)[1]
    except:
        return ""

def get_hostname():
    try:
        return socket.getfqdn().lower()
    except:
        return ""

def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False
    return True

def get_dns_servers():
    dns_ips = []
    with open('/etc/resolv.conf') as fp:
        for cnt, line in enumerate(fp):
            columns = line.split()
            if len(columns) == 0 :
                continue
            if columns[0] == 'nameserver':
                ip = columns[1:][0]
                if is_valid_ipv4_address(ip):
                    dns_ips.append(ip)
    return dns_ips

def host_info():
    """Read main workstation informations, returned as a dict

    Returns:
        dict: main properties of host, networking and windows system

    .. versionchanged:: 1.4.1
         returned keys changed :
           dns_domain -> dnsdomain

    >>> hi = host_info()
    >>> 'computer_fqdn' in hi and 'connected_ips' in hi and 'computer_name' in hi and 'mac' in hi
    True
    """
    info = {}
    try:
        dmi = dmi_info()

    ##    info['description'] = 'LINUX' ## inexistant in Linux
        info['system_manufacturer'] = dmi['System_Information']['Manufacturer']
        info['system_productname'] = dmi['System_Information']['Product_Name']
    except:
        logger.info('error while running dmidecode, dmidecode needs root privileges')
        pass

    info['computer_name'] = socket.gethostname()
    info['computer_fqdn'] = socket.getfqdn()
    info['dnsdomain'] = get_domain_batch()

    if os.path.isfile('/etc/samba/smb.conf'):
        config = configparser.RawConfigParser(strict=False)
        config.read('/etc/samba/smb.conf')
        if config.has_option('global','workgroup'):
            info['workgroup_name'] = config.get('global','workgroup')

    info['networking'] = networking()
    info['gateways'] = [get_default_gateways()]
    info['dns_servers'] = get_dns_servers()
    info['connected_ips'] = [get_main_ip()]
    info['mac'] = [ c['mac'] for c in networking() if 'mac' in c and 'addr' in c and c['addr'] in info['connected_ips']]
    info['linux64'] = isLinux64()
    info['kernel_version'] = get_kernel_version()
    info['distrib'] = get_distrib_linux()
    info['distrib_version'] = get_distrib_version()
    info['cpu_name'] = cpuinfo.get_cpu_info()['brand']
    if platform.system()=='Darwin':
        info['os_name']=platform.system()
        info['os_version']=platform.release()
    else:
        info['os_name'] = platform.linux_distribution()[0]
        info['os_version'] = platform.linux_distribution()[1]
    info['environ'] = {k:ensure_unicode(v) for k,v in os.environ.items()}
    info['main_ip'] = get_main_ip()
    info['platform'] = platform.system() if platform.system()!='Darwin' else 'macOS'

    return info

def get_computername():
    """Return host name (without domain part)"""
    return socket.gethostname()


def installed_softwares_macos(keywords='', uninstallkey=None, name=None):
    def get_file_type(file):
        path_file = file.replace(' ', '\ ')
        file_output = subprocess.check_output('file ' + path_file, shell=True)
        file_type = file_output.split(file)[1][2:-1] # Removing ": " and "\n"
        return file_type

    list_installed_softwares=[]

    app_dirs = [file for file in glob.glob('/Applications/*.app')]
    plist_files = [dirname + '/Contents/Info.plist' for dirname in app_dirs]

    for plist_file in plist_files:
        try:
            file_type = get_file_type(plist_file)

            if file_type == 'Apple binary property list':
                tmp_plist = '/tmp/info.plist'
                subprocess.call('plutil -convert xml1 ' + plist_file + ' -o ' + tmp_plist, shell=True)
                plist_obj = plistlib.readPlist(tmp_plist)
            else: # regular Plist
                plist_obj = plistlib.readPlist(plist_file)

            date_last_modif = os.path.getmtime(plist_file)
            date_last_modif = datetime.datetime.fromtimestamp(date_last_modif).strftime('%Y-%m-%d %H:%M:%S')
            infodict = {'key': '',
                        'name': plist_obj['CFBundleName'],
                        'version': plist_obj['CFBundleShortVersionString'],
                        'install_date': date_last_modif,
                        'install_location': plist_file[:plist_file.index('.app') + 4],
                        'uninstall_string': '',
                        'publisher': plist_obj['CFBundleIdentifier'].split('.')[1], # "com.publisher.name" => "publisher"
                        'system_component': ''}

            list_installed_softwares.append(infodict)
        except:
            print("Application data acquisition failed for {} :".format(plist_file))

    return list_installed_softwares

def installed_softwares(keywords='',uninstallkey=None,name=None):
    if apt:
        list_installed_softwares=[]
        for pkg in apt.Cache():
            path_dpkg_info ="/var/lib/dpkg/info/"
            if pkg.is_installed:
                try:
                    if os.path.isfile(os.path.join(path_dpkg_info,(pkg.name+'.list'))):
                        install_date=os.path.getctime(os.path.join(path_dpkg_info,(pkg.name+'.list')))
                    else:
                        install_date=os.path.getctime(os.path.join(path_dpkg_info,(pkg.fullname+'.list')))
                    install_date=datetime.datetime.fromtimestamp(install_date).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    install_date=''
                pkg_dict={'key':'','name':pkg.name,'version':str(pkg.installed).split('=',1)[1],'install_date':install_date,'install_location':'','uninstall_string':'','publisher':pkg.versions[0].homepage,'system_component':''}
                list_installed_softwares.append(pkg_dict)
        return list_installed_softwares
    elif rpm:
        list_installed_softwares=[]
        trans = rpm.TransactionSet()
        for header in trans.dbMatch():
            pkg_dict={'key':'','name':header['name'],'version':header['version'],'install_date':datetime.datetime.strptime(header.sprintf("%{INSTALLTID:date}"),'%a %b %d %H:%M:%S %Y').strftime('%Y-%m-%d %H:%M:%S'),'install_location':'','uninstall_string':'','publisher':header['url'],'system_component':''}
            list_installed_softwares.append(pkg_dict)
        return list_installed_softwares
    elif platform.system() == 'Darwin':
        return installed_softwares_macos(keywords, uninstallkey, name)
    else:
        return [{'key':'Distribution not supported yet', 'name':'Distribution not supported yet', 'version':'Distribution not supported yet', 'install_date':'Distribution not supported yet', 'install_location':'Distribution not supported yet', 'uninstall_string':'Distribution not supported yet', 'publisher':'Distribution not supported yet','system_component':'Distribution not supported yet'}]

def get_loggedinusers():
    suser = psutil.users()
    result = []
    for elem in suser:
        result.append(elem.name)
    return result

def get_last_logged_on_user():
    suser = psutil.users()
    res = ''
    for elem in suser:
        if res == '':
            res = elem
        elif res.started < elem.started:
            res = elem
    return res

def run(*args, **kwargs):
    return subprocess.check_output(shell=True,*args, **kwargs)

def apt_install(package,allow_unauthenticated=False):
    if allow_unauthenticated:
        return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get install -y --allow-unauthenticated %s' %package)
    else:
        return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get install -y %s' %package)

def apt_remove(package):
    return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get remove -y %s' %package)

def dpkg_install(path_to_deb):
    return run('LANG=C DEBIAN_FRONTEND=noninteractive dpkg -i %s' % path_to_deb)

def dpkg_purge(deb_name):
    return run('LANG=C DEBIAN_FRONTEND=noninteractive dpkg --purge %s' % deb_name)

def apt_install_required_dependencies():
    return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get -f -y install')

def apt_autoremove():
    return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get -y autoremove')

def yum_install(package):
    return run('LANG=C yum install -y %s' % package)

def yum_remove(package):
    return run('LANG=C yum remove -y %s' % package)

def yum_autoremove():
    return run('LANG=C yum autoremove -y')

def apt_update():
    return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get -y update')

def apt_upgrade():
    return run('LANG=C DEBIAN_FRONTEND=noninteractive apt-get -y upgrade')

def yum_update():
    return run('LANG=C yum update -y')

def yum_upgrade():
    return run('LANG=C yum upgrade -y')

def dmi_info():
    """Hardware System information from BIOS estracted with dmidecode
    Convert dmidecode -q output to python dict

    Returns:
        dict

    >>> dmi = dmi_info()
    >>> 'UUID' in dmi['System_Information']
    True
    >>> 'Product_Name' in dmi['System_Information']
    True
    """

    result = {}
    # dmidecode is bugged on macOS, and prints "Bad address" repeatedly on stderr
    if platform.system() != 'Darwin':
        dmiout = ensure_unicode(run('dmidecode -q'))
    else:
        dmiout = ensure_unicode(run('dmidecode -q 2> /dev/null'))

    new_section = True
    for l in dmiout.splitlines():
        if not l.strip() or l.startswith('#'):
            new_section = True
            continue

        if not l.startswith('\t') or new_section:
            currobject={}
            key = l.strip().replace(' ','_')
            # already here... so add as array...
            if (key in result):
                if not isinstance(result[key],list):
                    result[key] = [result[key]]
                result[key].append(currobject)
            else:
                result[key]  = currobject
            if l.startswith('\t'):
                print(l)
        else:
            if not l.startswith('\t\t'):
                currarray = []
                if ':' in l:
                    (name,value)=l.split(':',1)
                    currobject[name.strip().replace(' ','_')]=value.strip()
                else:
                    print("Error in line : %s" % l)
            else:
                # first line of array
                if not currarray:
                    currobject[name.strip().replace(' ','_')]=currarray
                currarray.append(l.strip())
        new_section = False
    return result


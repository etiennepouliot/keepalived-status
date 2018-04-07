#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
keepalived_staus.py
desc:
    check keeepalived.conf and status
updated: 2018-03-29
Mostly based on  https://github.com/etsxxx/keepalived-tools
'''
import os, sys, re
import glob
import optparse
import six

def_conf_path = '/etc/keepalived/keepalived.conf'

#if priority is greater than or equal to this value, ips should be active (MASTER) on the current host, can be overwritten with --priority
priority_master = 10

INFO_COLOR=u"\u001b[34m"
OK_COLOR=u"\u001b[32m"
WARN_COLOR=u"\u001b[33m"
NOTOK_COLOR=u"\u001b[31m"
RESET_COLOR=u"\u001b[0m"


regex_confline = re.compile(r'''^(?P<param>[^!#]+)(.*)$''', flags=re.IGNORECASE)
regex_include = re.compile(r'''^\s*include\s+(?P<path>[^\s]+).*$''', flags=re.IGNORECASE)


# config regex
regex_vrrp_instance = re.compile(r'''^\s*vrrp_instance\s+(?P<name>[^{\s]+).*$''', flags=re.IGNORECASE)
class VRRP_INSTANCE(dict):
    def __init__(self, name, index):
        dict.__init__(self)
        self['name'] = name
        self['index'] = index


regex_vrid = re.compile(r'''^\s*virtual_router_id\s+(?P<vrid>\d+).*$''', flags=re.IGNORECASE)
class VRID(dict):
    def __init__(self, vrid, index):
        dict.__init__(self)
        self['vrid'] = vrid
        self['index'] = index

regex_priority = re.compile(r'''^\s*priority\s+(?P<priority>\d+).*$''', flags=re.IGNORECASE)
class PRIORITY(dict):
    def __init__(self, priority, index):
        dict.__init__(self)
        self['priority'] = priority 
        self['index'] = index

regex_vip = re.compile(r'''^\s*(?P<vip>(\d{1,3}\.){3}\d{1,3}).*$''', flags=re.IGNORECASE)
class VIP(dict):
    def __init__(self, vip, index):
        dict.__init__(self)
        self['vip'] = vip
        self['index'] = index

regex_vs = re.compile(r'''^\s*virtual_server\s+(?P<vip>(\d{1,3}\.){3}\d{1,3})\s+(?P<port>\d+).*$''', flags=re.IGNORECASE)
class VirtrualServer(dict):
    def __init__(self, index, vip, port, proto='tcp'):
        dict.__init__(self)
        self['index'] = index
        self['vip'] = vip
        self['port'] = port
        self['proto'] = proto

regex_vsg = re.compile(r'''^\s*virtual_server_group\s+(?P<groupname>[^{\s]+).*$''', flags=re.IGNORECASE)
class VirtrualServerGroup(dict):
    def __init__(self, index, groupname):
        dict.__init__(self)
        self['index'] = index
        self['groupname'] = groupname

regex_vsg_endpoint = re.compile(r'''^\s*virtual_server\s+group\s+(?P<groupname>[^{\s]+).*$''', flags=re.IGNORECASE)
class VirtrualServerGroupEndpoint(dict):
    def __init__(self, index, groupname, proto='tcp'):
        dict.__init__(self)
        self['index'] = index
        self['groupname'] = groupname
        self['proto'] = proto

regex_protocol = re.compile(r'''^\s*protocol\s+(?P<proto>[^\s]+).*$''', flags=re.IGNORECASE)


class KeepalivedConfigChecker(object):
    conf_path = ""
    verbose = False

    vrrps = list()
    vrids = list()
    priorities = list()
    vips = list()
    virtual_servers = list()
    vsgs = list()
    vsg_endpoints = list()
    instance_dict = {}

    def __init__(self, conf_path, verbose=False):
        self.conf_path = conf_path
        self.verbose = verbose

    def __load(self, path=""):
        '''
        __load read configs with support include stetement,
        and remove comments or blank lines.
        returns:
            list of tupple(parameter, filename:index)
        '''
        conf_dir = os.path.dirname(path)

        try:
            num = 0
            config = list()

            if self.verbose:
                print("loading config file: '%s'" % path)
            for line in open(path):
                num += 1
                m = regex_confline.match(line)
                if m is None :
                    continue
                ### parse
                param = m.group('param').rstrip()
                m_include = regex_include.match(param)
                if m_include :
                    include_path = m_include.group('path')
                    for p in glob.glob('/'.join([conf_dir, include_path])):
                        config.extend(self.__load(p))
                else :
                    index = "%s:%i" % (path, num)
                    config.append((param, index))

            return config
        except Exception as e:
            raise e

    def parse_config(self):
        config = self.__load(path=self.conf_path)
        if self.verbose:
            print("loading config end")
            print("---")

        tmp_vs = None
        tmp_vsg = None
        tmp_vsg_endpoint = None
        in_vrrp = False
        current_vvrp = ''

        nested = 0

        for line, index in config:
            nested += line.count('{')
            nested -= line.count('}')
            if nested == 0:
                # append previous info
                if tmp_vs:
                    self.virtual_servers.append(tmp_vs.copy())
                    if self.verbose:
                        print("virtual_server: '%(vip)s:%(port)s/%(proto)s' defined" % tmp_vs)
                if tmp_vsg:
                    self.vsgs.append(tmp_vsg.copy())
                    if self.verbose:
                        print("virtual_server_group: '%(groupname)s' defined" % tmp_vsg)
                if tmp_vsg_endpoint:
                    self.vsg_endpoints.append(tmp_vsg_endpoint.copy())
                    if self.verbose:
                        print("virtual_server_group backend: '%(groupname)s' defined with proto %(proto)s" % tmp_vsg_endpoint)

                # reset parameters
                tmp_vs = None
                tmp_vsg = None
                tmp_vsg_endpoint = None
                in_vrrp = False
            elif nested < 0:
                print("Error: config structure maybe wrong at: %s" % line)


            # vrrp_instance
            m = regex_vrrp_instance.match(line)
            if m :
                vrrp = VRRP_INSTANCE(
                    name=m.group('name'),
                    index=index
                )
                self.vrrps.append(vrrp)
                if self.verbose:
                    print("vrrp_instance '%s' defined" % vrrp['name'] )
                current_vvrp=vrrp['name']
                self.instance_dict[current_vvrp] = {'vips': [] , 'priority' : None }
                in_vrrp = True
                continue

            if in_vrrp:
                # vrid
                m = regex_vrid.match(line)
                if m :
                    vrid = VRID(
                        vrid=m.group('vrid'),
                        index=index
                    )
                    self.vrids.append(vrid)
                    if self.verbose:
                        print("vrid: '%s' defined" % vrid['vrid'])

                    continue
                # priorities 
                m = regex_priority.match(line)
                if m :
                    priority = PRIORITY(
                        priority=m.group('priority'),
                        index=index
                    )
                    self.priorities.append(priority)
                    self.instance_dict[current_vvrp]['priority'] = priority['priority']
                    if self.verbose:
                        print("priority: '%s' defined" % priority['priority'])

                    continue
                # vip
                m = regex_vip.match(line)
                if m :
                    vip = VIP(
                        index=index,
                        vip=m.group('vip')
                    )
                    self.vips.append(vip)
                    self.instance_dict[current_vvrp]['vips'].append(vip['vip'])
                    if self.verbose:
                        print("vip: '%s' defined" % vip['vip'])
                    continue

            # virtual_server
            m = regex_vs.match(line)
            if m :
                tmp_vs = VirtrualServer(
                    vip=m.group('vip'),
                    port=m.group('port'),
                    index=index
                )
                continue

            # virtual_server_group
            m = regex_vsg.match(line)
            if m :
                tmp_vsg = VirtrualServerGroup(
                    index=index,
                    groupname=m.group('groupname')
                )

            # virtual_server_group endpoint
            m = regex_vsg_endpoint.match(line)
            if m :
                tmp_vsg_endpoint = VirtrualServerGroupEndpoint(
                    groupname=m.group('groupname'),
                    index=index
                )
                continue

            # virtual_server proto
            m = regex_protocol.match(line)
            if m :
                if tmp_vs:
                    tmp_vs['proto'] = m.group('proto').lower()
                    continue
                if tmp_vsg_endpoint:
                    tmp_vsg_endpoint['proto'] = m.group('proto').lower()


        # append previous info finally
        if tmp_vs:
            self.virtual_servers.append(tmp_vs.copy())
            if self.verbose:
                print("virtual_server: '%(vip)s:%(port)s/%(proto)s' defined" % tmp_vs)
        if tmp_vsg:
            self.vsgs.append(tmp_vsg.copy())
            if self.verbose:
                print("virtual_server_group: '%(groupname)s' defined" % tmp_vsg)
        if tmp_vsg_endpoint:
            self.vsg_endpoints.append(tmp_vsg_endpoint.copy())
            if self.verbose:
                print("virtual_server_group backend: '%(groupname)s' defined with proto %(proto)s" % tmp_vsg_endpoint)

        if self.verbose:
            print("config parse end")
            print("---")
        return


    def check_vrrps(self):
        dups_vrrps = self.__check_vrrps_dup()
        dups_vrids = self.__check_vrids_dup()
        return (len(dups_vrrps) + len(dups_vrids)) == 0

    def __check_vrrps_dup(self):
        vrrp_list = list( map(lambda x: x['name'], self.vrrps) )
        unique_list = list(set(vrrp_list))

        for ele in unique_list:
            vrrp_list.remove(ele)

        if len(vrrp_list) > 0 :
            print("'vrrp_instance' duplications found:")
            for ele in vrrp_list:
                print("\t" + ele)
                for vrrp in self.vrrps:
                    if vrrp['name'] != ele :
                        continue
                    print("\t\t- %s" % vrrp['index'])
            print
        return vrrp_list

    def __check_vrids_dup(self):
        vrid_list = list( map(lambda x: x['vrid'], self.vrids) )
        unique_list = list(set(vrid_list))

        for ele in unique_list:
            vrid_list.remove(ele)

        if len(vrid_list) > 0 :
            print("'virtual_router_id' duplications found:")
            for ele in vrid_list:
                print("\t" + ele)
                for vrid in self.vrids:
                    if vrid['vrid'] != ele :
                        continue
                    print("\t\t- %s" % vrid['index'])
            print
        return vrid_list


    def check_vips(self):
        dups_vip = self.__check_vips_dup()
        dups_vs = self.__check_vs_dup()
        ng_vips = self.__check_vips_unmanaged()
        return (len(dups_vip) + len(dups_vs) + len(ng_vips)) == 0

    def __check_vips_dup(self):
        vip_list = map(lambda x: x['vip'], self.vips)
        unique_list = list(set(vip_list))

        for ele in unique_list:
            vip_list.remove(ele)

        if len(vip_list) > 0 :
            print("'virtual_ipaddress' duplications found:")
            for ele in vip_list:
                print("\t" + ele)
                for vip in self.vips:
                    if vip['vip'] != ele :
                        continue
                    print("\t\t- %s" % vip['index'])
            print

        return vip_list

    def __check_vs_dup(self):
        vs_list = map(lambda x: (x['vip'], x['port'], x['proto']), self.virtual_servers)
        unique_list = list(set(vs_list))

        for ele in unique_list:
            vs_list.remove(ele)

        if len(vs_list) > 0 :
            print("'virtual_server' duplications found:")
            for ele in vs_list:
                print("\t%s:%s/%s" % (ele))
                for vs in self.virtual_servers:
                    if (vs['vip'], vs['port'], vs['proto']) != ele :
                        continue
                    print("\t\t- %s" % vs['index'])
            print

        return vs_list


    def __check_vips_unmanaged(self):
        managed_list = map(lambda x: x['vip'], self.vips)
        unmanaged_list = list()

        for vs in self.virtual_servers:
            if vs['vip'] not in managed_list :
                unmanaged_list.append(vs)

        if len(unmanaged_list) > 0 :
            print("'virtual_server' uses unmanaged VIP:")
            for ele in unmanaged_list:
                print("\t%(vip)s:%(port)s" % vs)
                print("\t\t- %(index)s" % vs)
            print

        return unmanaged_list



    def check_vsgs(self):
        dups_vsg = self.__check_vsgs_dup()
        dups_vsge = self.__check_vsg_endpoints_dup()
        ng_vsg_endpoints = self.__check_vsgs_unmanaged()
        return (len(dups_vsg) + len(dups_vsge) + len(ng_vsg_endpoints)) == 0


    def __check_vsgs_dup(self):
        vsg_list = map(lambda x: x['groupname'], self.vsgs)
        unique_list = list(set(vsg_list))

        for ele in unique_list:
            vsg_list.remove(ele)

        if len(vsg_list) > 0 :
            print("'virtual_server_group XXXXX' duplications found:")
            for ele in vsg_list:
                print("\t" + ele)
                for vsg in self.vsgs:
                    if vsg['groupname'] != ele:
                        continue
                    print("\t\t- %s" % vsg['index'])
            print

        return vsg_list

    def __check_vsg_endpoints_dup(self):
        vsge_list = map(lambda x: x['groupname'], self.vsg_endpoints)
        unique_list = list(set(vsge_list))

        for ele in unique_list:
            vsge_list.remove(ele)

        if len(vsge_list) > 0 :
            print("'virtual_server group XXXXX' duplications found:")
            for ele in vsge_list:
                print("\t" + ele)
                for vsge in self.vsg_endpoints:
                    if vsge['groupname'] != ele:
                        continue
                    print("\t\t- %s" % vsge['index'])
            print
        return vsge_list

    def __check_vsgs_unmanaged(self):
        managed_list = map(lambda x: x['groupname'], self.vsgs)
        unmanaged_list = list()

        for vsge in self.vsg_endpoints:
            if vsge['groupname'] not in managed_list :
                unmanaged_list.append(vsge)

        if len(unmanaged_list) > 0 :
            print("'virtual_server group' uses undefined group name:")
            for vsge in unmanaged_list:
                print("\t%(groupname)s:%(proto)s\t\t- %(index)s" % vsge)
            print

        return unmanaged_list




if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Check configuration and status of keepalived')
    parser.add_argument('--file', '-f', dest='conf_path', default=def_conf_path , help="set keepalived config file path. (default /etc/keepalived/keepalived.conf")
    parser.add_argument('--no-config-test', '-c', action='store_true',  help="Disable configuration test")
    parser.add_argument('--no-status-test', '-s', action='store_true', help="Disable status test")
    parser.add_argument('--verbose', '-v', action='store_true', help="verbose")
    parser.add_argument('--priority_master', '-p', type=int, default=priority_master, help="value at wich ips should currently be master")
    opts = parser.parse_args()
    checker = KeepalivedConfigChecker(conf_path=opts.conf_path, verbose=opts.verbose)
    checker.parse_config()

    ret = 0
    if opts.no_config_test == False :
        if not checker.check_vrrps():
            ret = 1
        if not checker.check_vips():
            ret = 1
        if not checker.check_vsgs():
            ret = 1

        if ret == 0 :
            print("{0}Config OK{1}".format(OK_COLOR,RESET_COLOR))
        else:
            print("{0}Config not good!{1}".format(NOTOK_COLOR,RESET_COLOR))
            if opts.no_status_test == False :
                print("{0}We won't check status{1}").format(NOTOK_COLOR,RESET_COLOR)
    if opts.no_status_test == False and ret == 0  :
        #we find out what ips are on this host
        ips = [] 
        import subprocess
        process = subprocess.Popen(['ip', 'addr'], stdout=subprocess.PIPE)
        out, err = process.communicate()
        if process.returncode == 0  :
            for line in out.split('\n') :
                ip = re.search(r"inet (\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)",line)
                if ip is not None :
                    ips.append(ip.groups()[0])
            for vrrp_name, conf in six.iteritems(checker.instance_dict ) :
                print(u"{0}Instance {1}{2}:".format(INFO_COLOR ,vrrp_name ,RESET_COLOR))
                if int(conf['priority'])  >= opts.priority_master : #ips should be on this host
                    for ip in conf['vips'] :
                        if ip in ips :
                            print(u"    {0}{1} is on this host (Expected){2}".format(OK_COLOR ,ip ,RESET_COLOR))
                        else :
                            print(u"    {0}{1} is not on this host (Unexpected){2}".format(NOTOK_COLOR ,ip ,RESET_COLOR))
                else :#ips should NOT be on this host
                    for ip in conf['vips']:
                        if ip in ips :
                            print(u"    {0}{1} is on this host (Unexpected){2}".format(NOTOK_COLOR ,ip ,RESET_COLOR))
                        else :
                            print(u"    {0}{1} is not on this host (Expected){2}".format(WARN_COLOR ,ip ,RESET_COLOR))

        else :
            raise SystemExit("ERR Could not determine local ips running 'ip addr'")
    sys.exit(ret)

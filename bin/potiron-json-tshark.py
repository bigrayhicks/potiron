#!/usr/bin/env python3


import subprocess
import os
import json
import sys
import potiron
import argparse
from potiron import infomsg
from potiron import errormsg
from potiron import check_program
import datetime
        

def store_packet(rootdir, pcapfilename, obj):
    if rootdir is not None:
        jsonfilename = potiron.get_file_struct(rootdir, pcapfilename)
        with open(jsonfilename, "w") as f:
            f.write(obj)
        infomsg("Created filename " + jsonfilename)
    else:
        sys.stdout.write(obj)
        
        
def create_dirs(rootdir, pcapfilename):
    jsonfilename = potiron.get_file_struct(rootdir, pcapfilename)
    d = os.path.dirname(jsonfilename)
    if not os.path.exists(d):
        os.makedirs(d)
        

def process_file(rootdir, filename):
    if not check_program("tshark"):
        raise OSError("The program tshark is not installed")
    # FIXME Put in config file
    if rootdir is not None:
        create_dirs(rootdir, filename)
    packet = {}
    sensorname = potiron.derive_sensor_name(filename)
    allpackets = []
    # Describe the source
    allpackets.append({"type": potiron.TYPE_SOURCE, "sensorname": sensorname,
                       "filename": os.path.basename(filename)})
    # Each packet as a incremental numeric id
    # A packet is identified with its sensorname filename and packet id for
    # further aggregation with meta data.
    # Assumption: Each program process the pcap file the same way?
    packet_id = 0
    proc = subprocess.Popen(["tshark", "-n", "-q", "-Tfields", "-e", "frame.time_epoch", "-e", "ip.len",
                             "-e", "ip.proto", "-e", "ip.src", "-e", "ip.dst", "-e", "ip.ttl", "-e", "ip.dsfield",
                             "-e", "tcp.srcport", "-e", "udp.srcport", "-e", "tcp.dstport", "-e", "udp.dstport", "-e", "tcp.seq",
                             "-e", "tcp.ack", "-e", "icmp.code", "-e", "icmp.type", "-E", "header=n", "-E", "separator=/s",
                             "-E", "occurrence=f", "-Y", potiron.tsharkfilter, "-r", filename,
                             "-o", "tcp.relative_sequence_numbers:FALSE"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in proc.stdout.readlines():
        packet_id = packet_id + 1
        line = line[:-1].decode()
        timestamp, length, protocol, ipsrc, ipdst, ipttl, iptos, tsport, usport, tdport, udport, tcpseq, tcpack, icmpcode, icmptype = line.split(' ')
        ilength = -1
        iipttl = -1
        iiptos = -1
        isport = -1
        idport = -1
        itcpseq = -1
        itcpack = -1
        iicmpcode = 255
        iicmptype = 255
        try:
            protocol = int(protocol)
        except ValueError:
            pass
        if protocol == 17:
            sport = usport
            dport = udport
        else:
            sport = tsport
            dport = tdport
        
        try:
            ilength = int(length)
        except ValueError:
            pass
        try:
            iipttl = int(ipttl)
        except ValueError:
            pass
        try:
            iiptos = int(iptos, 0)
        except ValueError:
            pass
        try:
            isport = int(sport)
        except ValueError:
            pass
        try:
            idport = int(dport)
        except ValueError:
            pass
        try:
            itcpseq = int(tcpseq)
        except ValueError:
            pass
        try:
            itcpack = int(tcpack)
        except ValueError:
            pass
        try:
            iicmpcode = int(icmpcode)
        except ValueError:
            pass
        try:
            iicmptype = int(icmptype)
        except ValueError:
            pass
        
        if ipsrc == '-':
            ipsrc = None
        if ipdst == '-':
            ipdst = None
        # Convert timestamp
        a, b = timestamp.split('.')
        dobj = datetime.datetime.fromtimestamp(float(a))
        stime = dobj.strftime("%Y-%m-%d %H:%M:%S")
        stime = stime + "." + b[:-3]
        packet = {'timestamp': stime,
                  'length': ilength,
                  'protocol': protocol,
                  'ipsrc': ipsrc,
                  'ipdst': ipdst,
                  'ipttl': iipttl,
                  'iptos': iiptos,
                  'sport': isport,
                  'dport': idport,
                  'tcpseq': itcpseq,
                  'tcpack': itcpack,
                  'icmpcode': iicmpcode,
                  'icmptype': iicmptype,
                  'packet_id': packet_id,
                  'type': potiron.TYPE_PACKET,
                  'state': potiron.STATE_NOT_ANNOATE
                  }
        # FIXME might consume a lot of memory
        allpackets.append(packet)
        
    # FIXME Implement polling because wait can last forever
    proc.wait()

    if proc.returncode != 0:
        errmsg = b"".join(proc.stderr.readlines())
        raise OSError("tshark failed. Return code {}. {}".format(proc.returncode, errmsg))
    store_packet(rootdir, filename, json.dumps(allpackets))
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Start the tool tshark and transform the output in a json document")
    parser.add_argument("-r", "--read", type=str, nargs=1, help="Compressed pcap file or pcap filename")
    parser.add_argument("-c", "--console", action='store_true', help="Log output also to console")
    parser.add_argument("-o", "--directory", nargs=1, help="Output directory where the json documents are stored")

    args = parser.parse_args()
    potiron.logconsole = args.console
    if args.read is not None:
        if os.path.exists(args.read[0]) is False:
            errormsg("The filename {} was not found".format(args.read[0]))
            sys.exit(1)

    if args.directory is not None and os.path.isdir(args.directory[0]) is False:
        errormsg("The root directory is not a directory")
        sys.exit(1)

    if args.read is None:
        errormsg("At least a pcap file must be specified")
        sys.exit(1)
    try:
        rootdir = None
        if args.directory is not None:
            rootdir = args.directory[0]
        process_file(rootdir, args.read[0])
    except OSError as e:
        errormsg("A processing error happend.{}.\n".format(e))
        sys.exit(1)
        

#!/usr/bin/env python
#
# Based on validae-files.py
#

"""Subversion pre-commit hook script that runs PMD static code analysis
on commited java files - commit will be rejected if PMD rules are voilated.
To avoid PMD checks - put NOPMD into SVN log.
The script expects a pmd-check.conf file placed in the conf dir under
the repo the commit is for."""

import sys
import os
import subprocess
import fnmatch
from string import Template

# Deal with the rename of ConfigParser to configparser in Python3
try:
    # Python >= 3.0
    import configparser
except ImportError:
    # Python < 3.0
    import ConfigParser as configparser

class Config(configparser.SafeConfigParser):
    """Superclass of SafeConfigParser with some customizations
    for this script"""
    def optionxform(self, option):
        """Redefine optionxform so option names are case sensitive"""
        return option

    def getlist(self, section, option):
        """Returns value of option as a list using whitespace to
        split entries"""
        value = self.get(section, option)
        if value:
            return value.split()
        else:
            return None

    def get_matching_rules(self, repo):
        """Return list of unique rules names that apply to a given repo"""
        rules = {}
        for option in self.options('repositories'):
            if fnmatch.fnmatch(repo, option):
                for rule in self.getlist('repositories', option):
                    rules[rule] = True
        return rules.keys()

    def get_rule_section_name(self, rule):
        """Given a rule name provide the section name it is defined in."""
        return 'rule:%s' % (rule)

class Commands:
    """Class to handle logic of running commands"""
    def __init__(self, config):
        self.config = config

    def svnlook_changed(self, repo, txn):
        """Provide list of files changed in txn of repo"""
        svnlook = self.config.get('DEFAULT', 'svnlook')
        cmd = "%s changed -t %s %s" % (svnlook, txn, repo)
        # sys.stderr.write("Command:: %s\n" % cmd)
        p = subprocess.Popen(cmd, shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        changed = []
        while True:
            line = p.stdout.readline()
            if not line:
                break
            line = line.decode().strip()
            text_mod = line[0:1]
            # Only if the contents of the file changed (by addition or update)
            # directories always end in / in the svnlook changed output
            if line[-1] != "/" and (text_mod == "A" or text_mod == "U"):
                changed.append(line[4:])

        # wait on the command to finish so we can get the
        # returncode/stderr output
        data = p.communicate()
        if p.returncode != 0:
            sys.stderr.write(data[1].decode())
            sys.exit(2)

        return changed

    def svnlook_getlog(self, repo, txn):
        """ Gets content of svn log"""
        svnlook = self.config.get('DEFAULT', 'svnlook')

        cmd = "%s log -t %s %s" % (svnlook, txn, repo)

        # sys.stderr.write(" Get log command: %s\n" % cmd)
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        data = p.communicate()

        return (p.returncode, data[0].decode())

    
    def svnlook_getfile(self, repo, txn, fn):
        """ Gets content of svn file"""
        svnlook = self.config.get('DEFAULT', 'svnlook')
        pmd_temp = self.config.get('DEFAULT', 'pmd_temp')

        cmd = "%s cat -t %s %s %s > %s" % (svnlook, txn, repo, fn, pmd_temp)

        # sys.stderr.write(" Get file command: %s\n" % cmd)
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        data = p.communicate()

        return (p.returncode, data[1].decode())

    def pmd_command(self, repo, txn, fn):
        """ Run the PMD scan over created temporary java file"""
        pmd = self.config.get('DEFAULT', 'pmd')
        pmd_temp = self.config.get('DEFAULT', 'pmd_temp')
        pmd_rules = self.config.get('DEFAULT', 'pmd_rules')

        cmd = "%s -f text -R %s -d %s" % (pmd, pmd_rules, pmd_temp)

        # sys.stderr.write("PMD command: %s\n" % cmd)
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        data = p.communicate()

        # pmd is not working on error codes ..
        return (p.returncode, data[0].decode())

    def user_command(self, section, repo, txn, fn):
        """ Run the command defined for a given section.
        Replaces $REPO, $TXN and $FILE with the repo, txn and fn arguments
        in the defined command.

        Returns a tuple of the exit code and the stderr output of the command"""
        cmd_template = self.config.get(section, 'command')
        cmd = Template(cmd_template).safe_substitute(REPO=repo,
                                                     TXN=txn, FILE=fn)
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE)
        data = p.communicate()
        return (p.returncode, data[1])

def main(repo, txn):
    exitcode = 0
    # sys.stderr.write("repo=%s & txn=%s" % (repo,txn))
    config = Config()
    config.read(os.path.join(repo, 'conf', 'pmd-check.conf'))
    commands = Commands(config)

    # check if someone put magic string to not process code with PMD
    (returncode, log) = commands.svnlook_getlog(repo, txn)
    if returncode != 0:
        sys.stderr.write(
            "\nError retrieving log from svn " \
            "(exit code %d):\n" % (returncode))
        sys.stderr.write(err_mesg)
        sys.exit(returncode);
        
    if log.find("NOPMD") != -1:
        sys.stderr.write("There will be no PMD check - mail should be sent instead.")
        sys.exit(exitcode)
        
    # get list of changed files during this commit
    changed = commands.svnlook_changed(repo, txn)

    # this shouldn't ever happen
    if len(changed) == 0:
    	sys.stderr.write("No files changed in SVN!!!\n")
        sys.exit(1)


    # only java files
    for fn in fnmatch.filter(changed, "*.java"):
        # sys.stderr.write(" File processed: %s \n" %fn  )
        (returncode, err_mesg) = commands.svnlook_getfile(repo,
                                                        txn, fn)
        if returncode != 0:
            sys.stderr.write(
                "\nError retrieving file '%s' from svn " \
                "(exit code %d):\n" % (fn, returncode))
            sys.stderr.write(err_mesg)
            
        (returncode, err_mesg) = commands.pmd_command(repo, txn, fn)
        if returncode != 0:
            sys.stderr.write(
                "\nError validating file '%s'" \
                "(exit code %d):\n" % (fn, returncode))
            sys.stderr.write(err_mesg)
            exitcode = 1
        if len(err_mesg) != 0:
            sys.stderr.write(
                "\nPMD violations in file '%s' \n" % fn)
            sys.stderr.write(err_mesg)
            exitcode = 1
            
    return exitcode

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write("invalid args\n")
        sys.exit(1)

    try:
        sys.exit(main(sys.argv[1], sys.argv[2]))
    except configparser.Error as e:
        sys.stderr.write("Error with the pmd-check.conf: %s\n" % e)
        sys.exit(1)

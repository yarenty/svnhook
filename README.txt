This is SVN - PMD check before commit code.
This is using standard SVN hooks, and is based on validate-files example.

Prerequisite:
- svn
- java
- python
- pmd 

Installation [WINDOWS]:
1) setup/create your SVN repository: "svnadmin create c:/workspace/svnrepo" 
2) copy pre-commit.py & pre-commit.bat into hooks directory "c:/workspace/svnrepo/hooks"
2a) check/update pre-commit.bat to point to your version of python/repository
3) copy pmd-check.conf into conf directory "c:/workspace/svnrepo/conf"
3a) check/update pmd-check.conf with proper paths to your apps: svn, pmd, 
and if you requie different pmd configuration

If you want to avoid PMD check - just put into comment "NOPMD"!

Have fun!
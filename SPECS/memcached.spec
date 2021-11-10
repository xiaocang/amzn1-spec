%define _buildid .15

%define username   memcached
%define groupname  memcached
%bcond_with tests
%bcond_with systemd

%if %{with systemd}
%global pid_dir /run/memcached
%else
%global pid_dir %{_localstatedir}/run/memcached
%endif

Name:           memcached
Version:        1.4.15
Release:        12%{?_buildid}%{?dist}
Epoch:          0
Summary:        High Performance, Distributed Memory Object Cache

Group:          System Environment/Daemons
License:        BSD
URL:            http://www.memcached.org/
Source0:        http://memcached.org/files/old/%{name}-%{version}.tar.gz

# custom unit file
Source1:        memcached.service
# custom init script
Source2:        memcached.sysv

# Patches
Patch001:       memcached-manpages.patch
Patch002:       memcached-CVE-2011-4971.patch
Patch003:       memcached-CVE-2013-0179_7290_7291.patch
Patch004:       memcached-CVE-2013-7239.patch
Patch005:       memcached-ipv6.patch
Patch006:       memcached-CVE-2016-8704_8705_8706.patch
Patch007:       memcached-segfault-issue-294.patch

# Amazon patches
# https://github.com/memcached/memcached/commit/dbb7a8af90054bf4ef51f5814ef7ceb17d83d974
Patch1000:      memcached-disable-udp-by-default.patch


# Fixes
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires:  git
BuildRequires:  libevent-devel
%if %{with tests}
BuildRequires:  perl(Test::More), perl(Test::Harness)
%endif
Requires(pre):  shadow-utils

%if %{with systemd}
BuildRequires:  systemd-units
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
# For triggerun
Requires(post): systemd-sysv
%else
Requires(post): /sbin/chkconfig
Requires(preun): /sbin/chkconfig, /sbin/service
Requires(postun): /sbin/service
%endif


# as of 3.5.5-4 selinux has memcache included
Obsoletes: memcached-selinux

%description
memcached is a high-performance, distributed memory object caching
system, generic in nature, but intended for use in speeding up dynamic
web applications by alleviating database load.

%package devel
Summary:    Files needed for development using memcached protocol
Group:      Development/Libraries
Requires:   %{name} = %{epoch}:%{version}-%{release}

%description devel
Install memcached-devel if you are developing C/C++ applications that require
access to the memcached binary include files.

%prep
%setup -q
%patch001 -p1 -b .manpages
%patch002 -p1 -b .CVE-2011-4971
%patch003 -p1 -b .CVE-2013-0179_7290_7291
%patch004 -p1 -b .CVE-2013-7239
%patch005 -p1 -b .ipv6
%patch006 -p1 -b .CVE-2016-8704_8705_8706
%patch007 -p1 -b .segfault-issue-294

# Amazon patches
%patch1000 -p1

%build
# compile with full RELRO
export CFLAGS="%{optflags} -pie -fpie"
export LDFLAGS="-Wl,-z,relro,-z,now"

%configure --enable-tls
sed -i 's/-Werror/ /' Makefile
make %{?_smp_mflags}

%check
%if %{with tests}
# whitespace tests fail locally on fedpkg systems now that they use git
rm -f t/whitespace.t

# Parts of the test suite only succeed as non-root.
if [ `id -u` -ne 0 ]; then
  # remove failing test that doesn't work in
  # build systems
  rm -f t/daemonize.t
fi
make test
%endif

%install
rm -rf %{buildroot}
make install DESTDIR=%{buildroot} INSTALL="%{__install} -p"
# remove memcached-debug
rm -f %{buildroot}/%{_bindir}/memcached-debug

# Perl script for monitoring memcached
install -Dp -m0755 scripts/memcached-tool %{buildroot}%{_bindir}/memcached-tool
install -Dp -m0644 scripts/memcached-tool.1 \
        %{buildroot}%{_mandir}/man1/memcached-tool.1

%if %{with systemd}
# Unit file
install -Dp -m0644 %{SOURCE1} %{buildroot}%{_unitdir}/memcached.service
%else
# Init script
install -Dp -m0755 %{SOURCE2} %{buildroot}%{_initrddir}/memcached
# pid directory
mkdir -p %{buildroot}/%{pid_dir}
%endif

# Default configs
mkdir -p %{buildroot}/%{_sysconfdir}/sysconfig
cat <<EOF >%{buildroot}/%{_sysconfdir}/sysconfig/%{name}
PORT="11211"
USER="%{username}"
MAXCONN="1024"
CACHESIZE="64"
OPTIONS=""
EOF

# Constant timestamp on the config file.
%if %{with systemd}
touch -r %{SOURCE1} %{buildroot}/%{_sysconfdir}/sysconfig/%{name}
%else
touch -r %{SOURCE2} %{buildroot}/%{_sysconfdir}/sysconfig/%{name}
%endif

%clean
rm -rf %{buildroot}


%pre
getent group %{groupname} >/dev/null || groupadd -r %{groupname}
getent passwd %{username} >/dev/null || \
useradd -r -g %{groupname} -d %{pid_dir} \
    -s /sbin/nologin -c "Memcached daemon" %{username}
exit 0


%post
%if %{with systemd}
%systemd_post memcached.service
%else
if [ $1 -eq 1 ]; then
    /sbin/chkconfig --add %{name}
fi
%endif

%preun
%if %{with systemd}
%systemd_preun memcached.service
%else
if [ "$1" = 0 ]; then
    /sbin/service %{name} stop >/dev/null 2>&1
    /sbin/chkconfig --del %{name}
fi
%endif
exit 0


%postun
%if %{with systemd}
%systemd_postun_with_restart memcached.service
%else
if [ "$1" -ge 1 ]; then
    /sbin/service %{name} condrestart > /dev/null 2>&1
fi
%endif
exit 0

%if %{with systemd}
%triggerun -- memcached < 0:1.4.13-2
# Save the current service runlevel info
# User must manually run systemd-sysv-convert --apply memcached
# to migrate them to systemd targets
/usr/bin/systemd-sysv-convert --save memcached >/dev/null 2>&1 ||:

# The SysV package does this if without systemd
/sbin/chkconfig --del memcached >/dev/null 2>&1 || :
/bin/systemctl try-restart memcached.service >/dev/null 2>&1 || :
%endif

%files
%defattr(-,root,root,-)
%doc AUTHORS ChangeLog COPYING NEWS README.md doc/CONTRIBUTORS doc/*.txt
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%{_bindir}/memcached-tool
%{_bindir}/memcached
%{_mandir}/man1/memcached-tool.1*
%{_mandir}/man1/memcached.1*
%if %{with systemd}
%{_unitdir}/memcached.service
%else
%dir %attr(755,%{username},%{groupname}) %{pid_dir}
%{_initrddir}/memcached
%endif


%files devel
%defattr(-,root,root,0755)
%{_includedir}/memcached/*

%changelog
* Wed Nov 10 2021 Johnny Wang <wangjiahao@openresty.com> - 0:1.4.15-12
- Enable tls.

* Sun Sep 27 2020 Johnny Wang <wangjiahao@openresty.com> - 0:1.4.15-11
- Issue 294: Check for allocation failure

* Thu Mar 1 2018 Iliana Weller <iweller@amazon.com>
- Disable UDP port by default

* Wed Nov 23 2016 Amazon Linux AMI <amazon-linux-ami@amazon.com>
- import source package EL7/memcached-1.4.15-10.el7_3.1

* Mon Nov 07 2016 Miroslav Lichvar <mlichvar@redhat.com> - 0:1.4.15-10.el7_3.1
- fix vulnerabilities allowing remote code execution (CVE-2016-8704,
  CVE-2016-8705, CVE-2016-8706)

* Thu Nov 3 2016 Amazon Linux AMI <amazon-linux-ami@amazon.com>
- import source package EL7/memcached-1.4.15-10.el7

* Mon Oct 31 2016 Ben Cressey <bcressey@amazon.com>
- add patch for bounds check

* Thu Sep 15 2016 Amazon Linux AMI <amazon-linux-ami@amazon.com>
- import source package EL7/memcached-1.4.15-9.el7_2.1

* Tue Mar 08 2016 Miroslav Lichvar <mlichvar@redhat.com> - 0:1.4.15-10
- fix binding to IPv6 address (#1298603)
- enable SASL support (#1263696)
- don't allow authentication with bad SASL credentials (CVE-2013-7239)

* Wed May 7 2014 Cristian Gafton <gafton@amazon.com>
- import source package RHEL7/memcached-1.4.15-9.el7

* Fri Jan 24 2014 Daniel Mach <dmach@redhat.com> - 01.4.15-9
- Mass rebuild 2014-01-24

* Tue Jan 14 2014 Miroslav Lichvar <mlichvar@redhat.com> - 0:1.4.15-8
- fix unbound key printing (CVE-2013-0179, CVE-2013-7290, CVE-2013-7291)

* Fri Dec 27 2013 Daniel Mach <dmach@redhat.com> - 01.4.15-7
- Mass rebuild 2013-12-27

* Fri Dec 13 2013 Cristian Gafton <gafton@amazon.com>
- import source package RHEL7/memcached-1.4.15-5.el7

* Thu Dec 12 2013 Miroslav Lichvar <mlichvar@redhat.com> - 0:1.4.15-6
- fix segfault on specially crafted packet (#988739, CVE-2011-4971)

* Mon Jul 08 2013 Miroslav Lichvar <mlichvar@redhat.com> - 0:1.4.15-5
- update memcached man page
- add memcached-tool man page
- buildrequire systemd-units

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:1.4.15-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Dec 20 2012 Miroslav Lichvar <mlichvar@redhat.com> - 0:1.4.15-3
- compile with full RELRO

* Tue Nov 20 2012 Joe Orton <jorton@redhat.com> - 0:1.4.15-2
- BR perl(Test::Harness)

* Tue Nov 20 2012 Joe Orton <jorton@redhat.com> - 0:1.4.15-1
- update to 1.4.15 (#782395)
- switch to simple systemd service (#878198)
- use systemd scriptlet macros (Václav Pavlín, #850204)

* Fri Jul 20 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:1.4.13-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri May 04 2012 Jon Ciesla <limburgher@gmail.com> - 0:1.4.13-2
- Migrate to systemd, 783112.

* Thu Mar 8 2012 Andrew Jorgensen <ajorgens@amazon.com>
- Update to 1.4.13

* Tue Feb  7 2012 Paul Lindner <lindner@mirth.inuus.com> - 0:1.4.13-1
- Upgrade to memcached 1.4.13
- http://code.google.com/p/memcached/wiki/ReleaseNotes1413
- http://code.google.com/p/memcached/wiki/ReleaseNotes1412
- http://code.google.com/p/memcached/wiki/ReleaseNotes1411

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:1.4.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Wed Nov  9 2011 Paul Lindner <lindner@mirth.inuus.com> - 0:1.4.10-1
- Upgrade to memcached 1.4.10 (http://code.google.com/p/memcached/wiki/ReleaseNotes1410)

* Tue Aug 16 2011 Paul Lindner <lindner@inuus.com> - 0:1.4.7-1
- Upgrade to memcached 1.4.7 (http://code.google.com/p/memcached/wiki/ReleaseNotes147)
- Fix some rpmlint errors/warnings.

* Wed Aug 3 2011 Cristian Gafton <gafton@amazon.com>
- update to version 1.4.6

* Tue Aug  2 2011 Paul Lindner <lindner@inuus.com> - 0:1.4.6-1
- Upgrade to memcached-1.4.6

* Wed Feb 16 2011 Joe Orton <jorton@redhat.com> - 0:1.4.5-7
- fix build

* Mon Feb 14 2011 Paul Lindner <lindner@inuus.com> - 0:1.4.5-6
- Rebuild for updated libevent

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0:1.4.5-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Tue Jan 18 2011 Cristian Gafton <gafton@amazon.com>
- don't run the tests that require a correctly configured networking setup in chroots

* Thu Dec 30 2010 Ben Howard <behoward@amazon.com>
- Build requries git, added

* Sun Nov 28 2010 Paul Lindner <lindner@inuus.com> - 0:1.4.5-4
- Add code to deal with /var/run/memcached on tmpfs

* Wed Sep  8 2010 Paul Lindner <lindner@inuus.com> - 0:1.4.5-3
- Apply patch from memcached issue #60, solves Bugzilla 631051

* Fri Jul 9 2010 Cristian Gafton <gafton@amazon.com>
- import source package RHEL6/memcached-1.4.4-3.el6
- import source package RHEL6/memcached-1.4.4-1.el6
- setup complete for package memcached

* Wed May 26 2010 Joe Orton <jorton@redhat.com> - 0:1.4.5-2
- LSB compliance fixes for init script
- don't run the test suite as root
- ensure a constant timestamp on the sysconfig file

* Sun Apr  4 2010 Paul Lindner <lindner@inuus.com> - 0:1.4.5-1
- Upgrade to upstream memcached-1.4.5 (http://code.google.com/p/memcached/wiki/ReleaseNotes145)

* Wed Jan 20 2010 Paul Lindner <lindner@inuus.com> - 0:1.4.4-2
- Remove SELinux policies fixes Bugzilla 557073

* Sat Nov 28 2009 Paul Lindner <lindner@inuus.com> - 0:1.4.4-1
- Upgraded to upstream memcached-1.4.4 (http://code.google.com/p/memcached/wiki/ReleaseNotes144)
- Add explicit Epoch to fix issue with broken devel dependencies (resolves 542001)

* Thu Nov 12 2009 Paul Lindner <lindner@inuus.com> - 1.4.3-1
- Add explicit require on memcached for memcached-devel (resolves 537046)
- enable-threads option no longer needed
- Update web site address

* Wed Nov 11 2009 Paul Lindner <lindner@inuus.com> - 1.4.3-1
- Upgrade to memcached-1.4.3

* Mon Oct 12 2009 Paul Lindner <lindner@inuus.com> - 1.4.2-1
- Upgrade to memcached-1.4.2
- Addresses CVE-2009-2415

* Sat Aug 29 2009 Paul Lindner <lindner@inuus.com> - 1.4.1-1
- Upgrade to 1.4.1
- http://code.google.com/p/memcached/wiki/ReleaseNotes141

* Wed Apr 29 2009 Paul Lindner <lindner@inuus.com> - 1.2.8-1
- Upgrade to memcached-1.2.8
- Addresses CVE-2009-1255

* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.2.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Tue Jul 29 2008 Paul Lindner <lindner@inuus.com> - 1.2.6-1
- Upgrade to memcached-1.2.6

* Tue Mar  4 2008 Paul Lindner <lindner@inuus.com> - 1.2.5-1
- Upgrade to memcached-1.2.5

* Tue Feb 19 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 1.2.4-4
- Autorebuild for GCC 4.3

* Sun Jan 27 2008 Paul Lindner <lindner@inuus.com> - 1.2.4-3
- Adjust libevent dependencies

* Sat Dec 22 2007 Paul Lindner <lindner@inuus.com> - 1.2.4-2
- Upgrade to memcached-1.2.4

* Fri Sep 07 2007 Konstantin Ryabitsev <icon@fedoraproject.org> - 1.2.3-8
- Add selinux policies
- Create our own system user

* Mon Aug  6 2007 Paul Lindner <lindner@inuus.com> - 1.2.3-7
- Fix problem with -P and -d flag combo on x86_64
- Fix init script for FC-6

* Fri Jul 13 2007 Paul Lindner <lindner@inuus.com> - 1.2.3-4
- Remove test that fails in fedora build system on ppc64

* Sat Jul  7 2007 root <lindner@inuus.com> - 1.2.3-2
- Upgrade to 1.2.3 upstream
- Adjust make install to preserve man page timestamp
- Conform with LSB init scripts standards, add force-reload

* Wed Jul  4 2007 Paul Lindner <lindner@inuus.com> - 1.2.2-5
- Use /var/run/memcached/ directory to hold PID file

* Sat May 12 2007 Paul Lindner <lindner@inuus.com> - 1.2.2-4
- Remove tabs from spec file, rpmlint reports no more errors

* Thu May 10 2007 Paul Lindner <lindner@inuus.com> - 1.2.2-3
- Enable build-time regression tests
- add dependency on initscripts
- remove memcached-debug (not needed in dist)
- above suggestions from Bernard Johnson

* Mon May  7 2007 Paul Lindner <lindner@inuus.com> - 1.2.2-2
- Tidyness improvements suggested by Ruben Kerkhof in bugzilla #238994

* Fri May  4 2007 Paul Lindner <lindner@inuus.com> - 1.2.2-1
- Initial spec file created via rpmdev-newspec

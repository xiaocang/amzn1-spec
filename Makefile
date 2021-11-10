# sudo yum install -y libtool spectool createrepo
TARGET ?= i386

.PHONY: all
all: openresty-zlib openresty-openssl111 memcached
	@echo "done"

memcached:
	spectool -C ~/rpmbuild/SOURCES/ -gf SPECS/memcached.spec
	rpmbuild -ba --target=$(TARGET) SPECS/memcached.spec

.PHONY: clean
clean:
	sudo yum remove -y openresty-zlib openresty-openssl111
	sudo rm -f /etc/yum.repos.d/local-base-i386.repo
	sudo rm -f /etc/yum.repos.d/local-base-i686.repo

/etc/yum.repos.d/local-base-$(TARGET).repo:
	@printf "[local-base-$(TARGET)]\n\
	name=Local Base Repo\n\
	baseurl=file://$$HOME/rpmbuild/RPMS/$(TARGET)/\n\
	skip_if_unavailable=True\n\
	gpgcheck=0\n\
	repo_gpgcheck=0\n\
	enabled=1\n\
	enabled_metadata=1\n" | sudo tee /etc/yum.repos.d/local-base-$(TARGET).repo

openresty-zlib: /etc/yum.repos.d/local-base-$(TARGET).repo
	spectool -C ~/rpmbuild/SOURCES/ -gf SPECS/openresty-zlib.spec
	rpmbuild -ba --target=$(TARGET) -ba SPECS/openresty-zlib.spec
	sudo createrepo --update ~/rpmbuild/RPMS/$(TARGET)
	sudo yum clean all
	sudo yum install -y openresty-zlib-devel

openresty-openssl111: /etc/yum.repos.d/local-base-$(TARGET).repo
	spectool -C ~/rpmbuild/SOURCES/ -gf SPECS/openresty-openssl111.spec
	rpmbuild -ba --target=$(TARGET) SPECS/openresty-openssl111.spec
	sudo createrepo --update ~/rpmbuild/RPMS/$(TARGET)
	sudo yum clean all
	sudo yum install -y openresty-openssl111-devel

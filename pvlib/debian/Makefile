NAME = sn-pvlib
DIST = 
VERSION = 1.3.0-1$(if $(DIST),+$(DIST),)
PATHS = usr var

deb : prep
	fpm -s dir -t deb \
		-n $(NAME) \
		-v $(VERSION) \
		-a all \
		-m 'packaging@solarnetwork.org.nz' \
		--vendor 'SolarNetwork Foundation' \
		--description 'SolarNode pvlib support' \
		--license 'Apache License 2.0' \
		-f \
		-d 'python3 (>= 3.9)' \
		-d 'python3-pip' \
		-d 'python3-venv' \
		-d 'libatlas3-base' \
		-d 'libgfortran5' \
		-d 'libaec0' \
		-d 'libhdf5-103' \
		-d 'libsz2' \
		--after-install $(NAME).postinst \
		$(PATHS)

prep : 
	find $(PATHS) -type f -name .DS_Store -delete

clean : 
	rm $(NAME)_$(VERSION)_all.deb

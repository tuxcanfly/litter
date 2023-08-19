# Makefile

# Name of the script
SCRIPT_NAME = main.py
COMMAND_NAME = litter

# Installation location
INSTALL_PATH = /usr/local/bin

install: $(SCRIPT_NAME)
	echo "#!/usr/bin/env python3" | cat - $(SCRIPT_NAME) > /tmp/litter
	mv /tmp/litter $(INSTALL_PATH)/$(COMMAND_NAME)
	chmod +x $(INSTALL_PATH)/$(COMMAND_NAME)

uninstall:
	rm -f $(INSTALL_PATH)/$(COMMAND_NAME)

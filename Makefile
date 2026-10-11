# Convenience wrapper; the official project root is track_2a/.
.DEFAULT_GOAL := help
.PHONY: help run test
help run test:
	$(MAKE) -C track_2a $@
%:
	$(MAKE) -C track_2a $@

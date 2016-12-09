
echo $(srcdir)

.PHONY: clean clean-pyc torrentsdir


# run by `make -f makefile` and just `make`
default: tracker peer1 peer2 peer3


clean-pyc:
	rm -f *.pyc
	rm -f *.pyo
	rm -rf __pycache__


clean: clean-pyc
	rm -rf ./torrents/
	rm -f ./tracker
	rm -rf ./peer*/


tracker: torrentsdir
	if ! [ -e ./tracker ] ; then cp ./server.py ./tracker ; fi


cp_preq: $(cp ../$(preq) .)



peer%: 
	mkdir ./$@
	for preq in apiutils.py trackerfile.py sillycfg.py ; do \
		cp ./$$preq ./$@/$$preq ; \
	done
	cp ./peer.py ./$@/peer


torrentsdir:
	mkdir torrents

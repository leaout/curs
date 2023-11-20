PARSER_PATH=$PWD/

bison -d -o  ${PARSER_PATH}SepratorParser.cpp --defines=${PARSER_PATH}SepratorParser.h ${PARSER_PATH}csv_seprator.yy -v
flex -o ${PARSER_PATH}SepratorScanner.cpp ${PARSER_PATH}csv_seprator.ll

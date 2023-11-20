%skeleton "lalr1.cc"
%language "c++"
%glr-parser
%debug
%start file
%define api.prefix {BaseSeoratorParser}
%define api.parser.class {SepratorParser}
%param { class BaseDriver& driver }
%define api.value.type variant
%define api.token.constructor
%define parse.assert
%define api.token.raw
%define api.token.prefix {TOK_}
%defines
%define parse.error verbose
%locations


%code requires {
    #include <string>
    #include "BaseDriver.h"
}

%{
#include <string>
#include <boost/algorithm/string.hpp>
#include "SepratorScanner.h"
#include "StringCooker.h"
#undef yylex
#define yylex driver.seprator_lexer->lex
%}

%token
    END 0                   "end"
    EOL	    	            "end of line"
    ;

%token <std::string>
    String                "String"
    Text            "Text"
    ;


%token Seprator NewLine;

%%

file    :   rows
        ;

rows    :   row                 {if(!driver.push_line()) return 0;}
        |   rows NewLine row       {if(!driver.push_line()) return 0;}
        ;

row     :   field
        |   row Seprator field
        ;

field   :   String  {
                $1 = std::move($1.substr(1,$1.size()-2));
                driver.parse_escape_character($1);
                driver.push_line_value($1);
            }
        |   Text {
                boost::trim($1);
                driver.push_line_value($1);
            }
        |   /* empty */ {
                driver.push_line_value("");
            }
        ;

%%


void BaseSeoratorParser::SepratorParser::error(const SepratorParser::location_type& l,
			    const std::string& m)
{
    driver.error(l, m, 9);
}

%{
#include <string>
#include "SepratorScanner.h"
#include "BaseDriver.h"
#include "SepratorParser.h"

typedef BaseSeoratorParser::SepratorParser::token token;
typedef BaseSeoratorParser::SepratorParser::token_type token_type;

#define yyterminate() return BaseSeoratorParser::SepratorParser::make_END(loc);
#define YY_NO_UNISTD_H
// Code run each time a pattern is matched.
#define YY_USER_ACTION  loc.columns(yyleng);

char global_seprator = '\t';
%}

%option c++
%option prefix="BaseSeoratorParser"
%option batch
%option debug
%option yywrap nounput
%option stack
%s seprator1 seprator2 seprator3 seprator4

U						        [\x80-\xbf]
U2						        [\xc2-\xdf]
U3						        [\xe0-\xef]
U4						        [\xf0-\xf4]
UONLY 				   	        {U2}{U}|{U3}{U}{U}|{U4}{U}{U}{U}

String         		   	        ["]([^"]|\\.)*["]

Text1                            [^\r\n\t]+
Seprator1                        [\t]

Text2                            [^\r\n,]+
Seprator2                        [,]

Text3                            [^\r\n;]+
Seprator3                        [;]

Text4                            [^\r\n|]+
Seprator4                        [|]

NewLine                      \n|\r\n

%%

%{
    // A handy shortcut to the location held by the driver.
      BaseSeoratorParser::location& loc = driver.m_location;
      // Code run each time yylex is called.
      loc.step ();
    if(driver.m_seprator == "\t") {
        BEGIN(seprator1);
    } else if(driver.m_seprator == ",") {
        BEGIN(seprator2);
    } else if(driver.m_seprator == ";") {
        BEGIN(seprator3);
    } else if(driver.m_seprator == "|") {
        BEGIN(seprator4);
    } else {
        BEGIN(seprator2);
    }
%}

{String} {
    //yylval->stringVal = new std::string(yytext, yyleng);
    //return token::String;
    return BaseSeoratorParser::SepratorParser::make_String(string(yytext,yyleng), loc);
}

<seprator1>{Seprator1} {
    //return token::Seprator;
    return BaseSeoratorParser::SepratorParser::make_Seprator(loc);
}

<seprator1>{Text1} {
    //yylval->stringVal = new std::string(yytext, yyleng);
    //return token::Text;
    return BaseSeoratorParser::SepratorParser::make_Text(string(yytext,yyleng), loc);
}

<seprator2>{Seprator2} {
    return BaseSeoratorParser::SepratorParser::make_Seprator(loc);
}

<seprator2>{Text2} {
    //yylval->stringVal = new std::string(yytext, yyleng);
    //return token::Text;
    return BaseSeoratorParser::SepratorParser::make_Text(string(yytext,yyleng), loc);
}

<seprator3>{Seprator3} {
    return BaseSeoratorParser::SepratorParser::make_Seprator(loc);
}

<seprator3>{Text3} {
    //yylval->stringVal = new std::string(yytext, yyleng);
    //return token::Text;
    return BaseSeoratorParser::SepratorParser::make_Text(string(yytext,yyleng), loc);
}

<seprator4>{Seprator4} {
    return BaseSeoratorParser::SepratorParser::make_Seprator(loc);
}

<seprator4>{Text4} {
    //yylval->stringVal = new std::string(yytext, yyleng);
    //return token::Text;
    return BaseSeoratorParser::SepratorParser::make_Text(string(yytext,yyleng), loc);
}

{NewLine} {
    return BaseSeoratorParser::SepratorParser::make_NewLine(loc);
}

%%

namespace BaseSeoratorParser {

    SepratorScanner::SepratorScanner(std::istream* in,
             std::ostream* out)
        : BaseSeoratorParserFlexLexer(in, out)
    {
    }

    SepratorScanner::~SepratorScanner()
    {
    }

    void SepratorScanner::set_debug(bool b)
    {
        yy_flex_debug = b;
    }

}

#ifdef yylex
#undef yylex
#endif

int BaseSeoratorParserFlexLexer::yylex()
{
    std::cerr << "in BaseSeoratorParserFlexLexer::yylex() !" << std::endl;
    return 0;
}

int BaseSeoratorParserFlexLexer::yywrap()
{
    return 1;
}

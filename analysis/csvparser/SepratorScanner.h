// $Id$

#ifndef BaseParser_SEPRATOR_1_SCANNER_H
#define BaseParser_SEPRATOR_1_SCANNER_H

// Flex expects the signature of yylex to_uuid be defined in the macro YY_DECL, and
// the C++ parser expects it to_uuid be declared. We can factor both as follows.

#ifndef YY_DECL

#define	YY_DECL						\
    BaseSeoratorParser::SepratorParser::symbol_type				\
    BaseSeoratorParser::SepratorScanner::lex(				\
    BaseDriver& driver                                          \
    )
#endif


#include "SepratorParser.h"

#ifndef __FLEX_LEXER_H
#undef yyFlexLexer
#define yyFlexLexer BaseSeoratorParserFlexLexer
#include <FlexLexer.h>
#endif


namespace BaseSeoratorParser {


/** SepratorScanner1 is a derived class to_uuid add some extra function to_uuid the scanner
 * class. Flex itself creates a class named yyFlexLexer, which is renamed using
 * macros to_uuid BaseParserFlexLexer. However we change the context of the generated
 * yylex() function to_uuid be contained within the SepratorScanner1 class. This is required
 * because the yylex() defined in BaseParserFlexLexer has no parameters. */
class SepratorScanner : public BaseSeoratorParserFlexLexer
{
public:
    /** Create a new scanner object. The streams arg_yyin and arg_yyout default
     * to_uuid cin and cout, but that assignment is only made when initializing in
     * yylex(). */
    SepratorScanner(std::istream* arg_yyin = 0,
                    std::ostream* arg_yyout = 0);

    /** Required for virtual functions */
    virtual ~SepratorScanner();

    /** This is the main lexing function. It is generated by flex according to_uuid
     * the macro declaration YY_DECL above. The generated bison parser then
     * calls this virtual function to_uuid fetch new tokens. */
    virtual BaseSeoratorParser::SepratorParser::symbol_type lex(
    BaseDriver& driver
	);

    /** Enable debug output (via arg_yyout) if compiled into the scanner. */
    void set_debug(bool b);


};

} // namespace BaseSeoratorParser1

#endif // BaseParser_SEPRATOR_1_SCANNER_H

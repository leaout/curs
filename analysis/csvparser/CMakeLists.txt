cmake_minimum_required(VERSION 3.10)

aux_source_directory(. DIR_CSV_PARSER)


add_library(csv_parser ${DIR_CSV_PARSER})


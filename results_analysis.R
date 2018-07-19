setwd("/home/irene/Repos/car-insurance-tool/")

data <- read.table("loxodon_results.csv", sep=",", header=T)
data <- read.table("loxodon_results_image_processing.csv", sep=",", header=T)
data <- read.table("loxodon_results_image_processing2.csv", sep=",", header=T)
data <- read.table("loxodon_results_image_processing3.csv", sep=",", header=T)
data <- read.table("loxodon_results_image_processing5.csv", sep=",", header=T)


head(data)
nrow(data)
summary(data)
subset(data, is.na(prediction_rank)) # 10 not found, out of which 9 are "valid" files

data_not_na <- subset(data, !is.na(prediction_rank))
summary(data_not_na)

table(as.character(data_not_na$video_file), data_not_na$exists_in_rdw) # for 3 videos, none of the found matches exist in RDW

library(plyr)

ddply(data_not_na, .(video_file), function(DF) DF[DF$confidence == max(DF$confidence),]) # all of the found plate numbers (having highest confidence) that have 6 symbols, seem correct

ddply(subset(data_not_na, exists_in_rdw=="Exists"), .(video_file), function(DF) DF[DF$confidence == max(DF$confidence),]) # all of the found plate numbers (having highest confidence) that have 6 symbols, seem correct

subset(data_not_na, video_file=="WhatsApp Video 2017-08-04 at 08.32.09")
# However, plate KV264G (WhatsApp Video 2017-08-04 at 11.04.25) seems correct from video, but not found in RDW

missing <- c("20170806_125958", "WhatsApp Video 2017-08-04 at 07.21.36", "WhatsApp Video 2017-08-04 at 08.31.43", "WhatsApp Video 2017-08-04 at 08.32.09", "WhatsApp Video 2017-08-04 at 08.32.59")

ddply(subset(data_not_na, exists_in_rdw=="Exists" & video_file %in% missing), .(video_file), function(DF) DF[DF$confidence == max(DF$confidence),]) # now we found additional 2 true positives

# Still, best RDW-existing match for WhatsApp Video 2017-08-04 at 08.31.43 is "1STV84", but true value is "4STV84"

still_missing <- c("WhatsApp Video 2017-08-04 at 08.31.43", "WhatsApp Video 2017-08-04 at 08.32.09", "WhatsApp Video 2017-08-04 at 08.32.59")

"4STV84" %in% unique(subset(data_not_na, video_file==still_missing[1])$plate_nr) # found "JSTV84", e.g. "4" was mistaken with "J"
"04PKKJ" %in% unique(subset(data_not_na, video_file==still_missing[2])$plate_nr) # found "0JPKKJ", e.g. "4" was mistaken with "J"
"91SNS8" %in% unique(subset(data_not_na, video_file==still_missing[3])$plate_nr) # nothing reasonable found ("8" is mistaken for "E" and "1" is not noticed)

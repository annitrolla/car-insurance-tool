setwd("Projects/Loxodon/car-insurance-tool")
library(data.table)
library(tidyverse)
library(lubridate)


dt <- read.table("loxodon_results_image_processing.csv", header=T, sep=',')

table(dt_preproc$is_valid_file)
length(unique(dt$video_file)) # 51 unique files

car_found <- group_by(dt, video_file) %>%
  count(exists_in_rdw)
car_found <- mutate(car_found, at_least_one_exists = ifelse(exists_in_rdw == 'Exists' & n>0, 1, 0)) %>%
  group_by(video_file) %>% summarise(at_least_one_exists=sum(at_least_one_exists, na.rm=T))

ggplot(car_found, aes(x=exists_in_rdw, fill=exists_in_rdw, y=n)) + geom_bar(position='dodge', stat='identity') + 
  theme_bw() + facet_wrap(~video_file, scales = 'free_y')

cars_not_found <- filter(car_found, at_least_one_exists==0)
cars_found <- filter(car_found, at_least_one_exists==1)

res <- filter(dt, video_file %in% cars_found$video_file & exists_in_rdw == 'Exists') %>%
  group_by(video_file) %>%
  filter(confidence == max(confidence, na.rm=T))

Mode <- function(x) {
  ux <- unique(x)
  ux[which.max(tabulate(match(x, ux)))]
}


res$max_is_right <- c(1,0,1,1,1,0,1,1,1,1,0,1,1,1,1,1,0,1,1,1,1,1,1,0)
lower_conf <- filter(dt, video_file %in% filter(res, max_is_right==0)$video_file) %>%
  filter(exists_in_rdw == 'Exists') %>%
  group_by(video_file) %>%
  filter(plate_nr == Mode(plate_nr))
res$mode_is_right <- c(NA,0,NA,NA,NA,0,rep(NA, 4),0,rep(NA, 5),0,rep(NA, 6),0)

as.data.frame(select(lower_conf, video_file, plate_nr))
# 20170806_125958 - none is right, 9SJS69
# 20170806_130214 - one is right  GT233K    80.9242
# Edited video -  7KDN41    80.7277
# VID_20170815_183919   7KDN41    80.5316
# WhatsApp Video 2017-08-04 at 08.32.59   none is right 91SNS8
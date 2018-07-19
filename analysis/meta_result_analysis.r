setwd("car-insurance-tool")
library(data.table)
library(tidyverse)
library(lubridate)


dt <- fread("metadata_results.csv")
dt <- mutate(dt, edited = as.factor(ifelse(video_file == "Edited video", 1, 0))) %>%
  mutate(FileSize = as.numeric(tstrsplit(`File Size`, split = ' ')[[1]])) 
dt <- mutate(dt, TrackDuration = ifelse(tstrsplit(`Track Duration`, split = ' ')[[2]]=='s',
                                        as.numeric(tstrsplit(`Track Duration`, split = ' ')[[1]]),
                                        0))

dt$file_nr <- 1:nrow(dt)
dt <- mutate(dt,TrackDuration = ifelse(edited==1, 30, TrackDuration))
dt$ratio <- dt$FileSize/dt$TrackDuration
ggplot(dt, aes(x=file_nr, y=ratio, color=edited)) + geom_point(size=3) + theme_bw()


dt_selected <- dt[, c(1,4,5,6,7,8,10,13,14,15,21,24,25,26,27,28,30,37,43,
                      45,49,50,51,54,55,56,57,58,61,64,69,73,74,75,76,77,79,87,
                      88,92,93,94,97,100,101,103,104,106,111,112,113,115,116,121,
                      122,123,124,130,140,142,143,146,148,154,157,163,
                      165,170,171,172,173,174)]
#clean(dt_selected)

dt_clean <- mutate(dt_selected, is_GPSLon = ifelse(is.na(`GPS Longitude`)==T, 'none', 'exists'),
                   `GPS Longitude` = NULL, `File Size`=NULL,
                   MediaModifiedDate = parse_date_time(`Media Modify Date`,"%Y:%m:%d %H:%M:%S"),
                   `Media Modify Date` = NULL, 
                   `Metering Mode`=NULL, AudioFormat = as.factor(`Audio Format`), `Audio Format`=NULL,
                   `White Balance`=NULL, MediaCreateDate = parse_date_time(`Media Create Date`,"%Y:%m:%d %H:%M:%S"),
                   `Media Create Date` = NULL, `Exposure Compensation`=NULL, `Shutter Speed`=NULL,
                   `X Resolution`=NULL, Software=NULL, `Media Language Code`=NULL)

dt_clean <- mutate(dt_clean, ModifiedDate = parse_date_time(`Modify Date`,"%Y:%m:%d %H:%M:%S"),
                   `Modify Date` = NULL,
                   `Exposure Mode` = NULL,
                   is_PurchaseFileFormat = as.factor(ifelse(is.na(`Purchase File Format`)==T, "none", "exists")),
                   `Purchase File Format` = NULL, `GPS Time Stamp`=NULL,
                   `GPS Date Stamp`=NULL,
                   is_CompressorName = as.factor(ifelse(is.na(`Compressor Name`)==T, "none", "exists")),
                   `Compressor Name` = NULL, `Time To Sample Table`=NULL,
                   is_Encoder = ifelse(is.na(Encoder)==T, 'none','exists'),
                   `Track Duration`= NULL, is_PixelApsectRatio = ifelse(is.na(`Pixel Aspect Ratio`)==T,'none','exists'),
                   `Pixel Aspect Ratio`=NULL, `Max Aperture Value` = NULL)

dt_clean <- mutate(dt_clean, MediaDuration=as.numeric(tstrsplit(`Media Duration`, split = ' ')[[1]]),
                   `Media Duration`=NULL)

dt_clean <- mutate(dt_clean, `Color Space`=NULL, CreateDate=parse_date_time(`Create Date`,"%Y:%m:%d %H:%M:%S"),
                   `Create Date` = NULL, Balance = NULL, `File Type Extension`=NULL,
                   `Date/Time Original` = NULL, `Current Time`=NULL, 
                   TrackCreateDate=parse_date_time(`Track Create Date`,"%Y:%m:%d %H:%M:%S"),
                   `Track Create Date` = NULL, `Bits Per Sample`=NULL,
                   `Scene Capture Type` = NULL, `Interoperability Index` = NULL,
                   is_ColorRepresenation = as.factor(ifelse(is.na(`Color Representation`)==T, "none", "exists")),
                   `Color Representation` = NULL)
dt_clean <- mutate(dt_clean, `Graphics Mode` = NULL, `Exposure Time`=NULL, `Color Components`=NULL,
                   `Hyperfocal Distance`=NULL, `Movie Data`=NULL, `Compression`=NULL,
                   is_GPSPos = ifelse(is.na(`GPS Position`)==T, 'none', 'exists'),
                   `GPS Position` = NULL, Duration=ifelse(tstrsplit(Duration, split = ' ')[[2]]=='s',
                                                          as.numeric(tstrsplit(Duration, split = ' ')[[1]]),
                                                          ifelse(edited==1, 30, NA)))

dt_clean <- mutate(dt_clean, AvgBitrate=ifelse(tstrsplit(`Avg Bitrate`, split = ' ')[[2]]=='Mbps', 
                                               as.numeric(tstrsplit(`Avg Bitrate`, split = ' ')[[1]]),
                                               NA))
                   
dt_clean <- mutate(dt_clean, `Avg Bitrate`=NULL, Orientation=NULL,
                   `Focal Length`=NULL, 
                   is_GPSCoordinates = ifelse(is.na(`GPS Coordinates`)==T, 'none', 'exists'),
                   `GPS Coordinates` = NULL, `Field Of View` = NULL, 
                   `GPS Altitude` = NULL, `Brightness Value` = NULL,
                   `GPS Date/Time` = NULL, 
                    TrackModifiedDate=parse_date_time(`Track Modify Date`,"%Y:%m:%d %H:%M:%S"),
                   `Track Modify Date` = NULL, 
                    is_GPSLat = ifelse(is.na(`GPS Latitude`)==T, 'none', 'exists'),
                   `GPS Latitude` = NULL, `Aperture Value` = NULL, `Audio Channels` = NULL)

dt_clean <- mutate(dt_clean, `Bit Depth`= NULL)
dt_clean$CompatibleBrands = dt_clean$`Compatible Brands`
dt_clean$MovieDataSize = dt_clean$`Movie Data Size`
dt_clean$HandlerType <- dt_clean$`Handler Type`
dt_clean$HandlerDescription <- dt_clean$`Handler Description`
dt_clean <- mutate(dt_clean, creation_modification_diff = MediaModifiedDate-MediaCreateDate) 
dt_clean <- mutate(dt_clean, is_MediaModifiedDate = ifelse(is.na(MediaModifiedDate)==T,'none','exists'),
                   is_MediaCreateDate = ifelse(is.na(MediaCreateDate)==T,'none','exists'))
dt_clean$is_Duration <- ifelse(is.na(dt_clean$Duration)==T, 'none','exists')
dt_clean$is_CreateDate <- ifelse(is.na(dt_clean$CreateDate)==T, 'none','exists')
dt_clean$is_ModifiedDate <- ifelse(is.na(dt_clean$ModifiedDate)==T, 'none','exists')
dt_clean$is_MediaDuration <- ifelse(is.na(dt_clean$MediaDuration)==T, 'none','exists')
dt_clean$is_AvgBitRate <- ifelse(is.na(dt_clean$AvgBitrate)==T, 'none','exists')
dt_only_different <- select(dt_clean, video_file, CompatibleBrands, is_Encoder,
                            MovieDataSize, HandlerType, is_Duration, HandlerDescription,
                            FileSize, TrackDuration, is_GPSLon, is_GPSLat, is_MediaModifiedDate,
                            is_MediaCreateDate, is_ModifiedDate, is_PurchaseFileFormat,
                            is_CompressorName, is_PixelApsectRatio, is_MediaDuration, is_CreateDate,
                            is_ColorRepresenation, is_GPSPos,
                            is_AvgBitRate, is_GPSCoordinates, edited)  



ggplot(dt_clean, aes(x=`Image Height`, y=`Image Width`, color=edited)) +
  geom_point(alpha=0.3) + theme_bw() + geom_jitter()

ggplot(dt_clean, aes(x=`Compatible Brands`, fill=edited)) + 
  geom_bar(position='dodge') + theme_bw()

ggplot(dt_clean, aes(x=Encoder, fill=edited)) + 
  geom_bar(position='dodge') + theme_bw()

ggplot(dt_clean, aes(x=`Movie Data Size`, y=`Movie Data Offset`, color=edited)) +
  geom_point(alpha=0.3) + theme_bw() + geom_jitter()

ggplot(dt_clean, aes(x=MediaDuration, y=AvgBitrate, color=edited)) +
  geom_point(alpha=0.3) + theme_bw() + geom_jitter()

table(dt_clean$`Handler Type`, dt_clean$edited)
table(dt_clean$`Image Size`, dt_clean$edited)
table(dt_clean$`Handler Description`, dt_clean$edited)
table(dt_clean$Rotation, dt_clean$edited)
table(dt_clean$GPSLon, dt_clean$edited)
table(dt_clean$is_MediaModifiedDate, dt_clean$edited)
table(dt_clean$AudioFormat, dt_clean$edited)
table(dt_clean$is_PurchaseFileFormat, dt_clean$edited)
table(dt_clean$CompatibleBrands, dt_clean$edited)
ggplot(dt_clean, aes(x=MovieDataSize, y=Duration, color=edited)) +
  geom_point(alpha=0.3, size=3) + theme_bw() + geom_jitter()

ggplot(dt_clean, aes(y=TrackDuration, x=file_nr, color=edited)) +
  geom_point(alpha=0.3, size=3) + theme_bw() + geom_jitter()

dt_clean$HandlerDescription

filter(dt_only_different, video_file=='20170806_125933')
           

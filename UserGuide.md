# DeskTranslate User Guide

Welcome to DeskTranslate, a live, seamless OCR translation tool right on your desktop!

## Contents page

* [Introduction](#introduction)
* [Quick Start](#quick-start)
* [Features](#features)
  * [Translation](#translation)
    * [Selecting languages](#selecting-languages)
    * [Selecting Borders](#selecting-borders)
    * [Auto Translate](#auto-translate)
  * [Customization](#customization) 
  * [Bonus Features](#bonus-features)
    * [Splash Screen](#splash-screen)
    * [Text Box Resizing](#text-box-resizing)
* [FAQ](#faq)


## Introduction

DeskTranslate is a desktop application for translating foreign texts using optical character recognition. 

It has 3 main features:

* Live-translation
* Text2Speech
* Customizable font sizes and colours

-> Do note that DeskTranslate is currently only available in Windows.

## Quick Start

![](images/githubDownload.png)

1. To get started, download DeskTranslate at our main repo by clicking Code -> Download ZIP.

2. Ensure Python is install in your computer.

3. Using terminal, go to the directory where the repo is downloaded to. 

4. Download the libraries required:  
`pip install -r requirements.txt`

5. Visit [this link](https://github.com/UB-Mannheim/tesseract/wiki) to download Tesseract v5.0.0, in order 
for our program to work on your computer.

6. At the installation wizard, check all boxes to ensure that all language training data will be included for DeskTranslate. 

7. Next, enter the following command to start the program:
`python main.py`

## Features 

* DeskTranslate has a intuitive GUI that is quite easy to use, with a customizable display
* Included a splash screen, in-app user guide, and about us section as well

### Translation

#### Selecting Languages
![](images/select_languages.gif)
Click the dropdown lists and either type in the first few characters of the language you are searching for or scroll down and click it to select.

#### Selecting Borders
![](images/select_border.gif)
Click on the `Select Borders` button on the Translate tab to start the selection. You can then draw a rectangle to indicate the where the text you would like to translate will be.

#### Auto Translate
![](images/DeskTranslate_zoom_BG_3.gif)
After selecting the borders, click the `Translate` button on the Translate tab. The app will automatically begin the OCR and translation process, and the translated text will be regularly updated in the translation window.

### Customization
To improve accessibility, we have enabled the user to customize certain features of the app as well as enable text to speech.

![](images/DeskTranslate_zoom_BG_2.gif)

#### Font Size

#### Translate Window Opacity

#### Text Color

#### Translator Engine

#### Narration



### Bonus Features
Additional features we added to improve the look and feel of the application

#### Splash Screen
![](images/DeskTranslate_zoom_BG_4.gif)
We added an animated splash screen to make the app look more profesional

#### Text Box Resizing
![](images/stretch_window.gif)
We enabled dynamic text box resizing to make it easier for the user to position and arrange the windows


## FAQ
**Q**: Is the app free to use?
**A**: Yes it is! 

**Q**: Do I need to have an internet connection for the app to work?
**A**: Yes, since the translation engines rely on API calls to online translators to work.



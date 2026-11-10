# Mini-Librarian
Mini-Librarian is a privacy focused search AI agent based on MiniCPM5-2B, indented to be used locally. By default It will search the folder "study_cards" for your search query and if nothing is found it will automatically search the web, using brave search and duck duck go.

## Privacy and Transparency
Mini-Librarian prioritizes searching your own "study_cards" folder first, and you are encouraged to create study_cards for often searched subjects, MiniCPM5-Librarian uses the privacy focused search engines: [Brave Search](https://search.brave.com/) and [DuckDuckGo](https://duckduckgo.com/) when searching online and by default your data is not sent to any AI provider, and the answer to your query is processed locally on your machine. each step the agent took to reach the answer is also presented in a flow-chart along with sources. 

![alt text](https://github.com/Rumidom/MiniCPM5-Librarian/blob/main/images/Screenshot_2026-11-10%2018-33-34.png)
![alt text](https://github.com/Rumidom/MiniCPM5-Librarian/blob/main/images/Screenshot_2026-11-10%2018-32-48.png)

## Install
### Linux
run ```run.sh``` then access [http://127.0.0.1:5000/](http://127.0.0.1:5000/) on your browser.

### Windows
run ```run.bat``` then access [http://127.0.0.1:5000/](http://127.0.0.1:5000/) on your browser.

## License
Mini-Librarian was made using GLM 4.6(Big Pickle) and is MIT licensed

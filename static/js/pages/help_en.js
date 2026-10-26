// Ajuda em inglês: o mesmo conteúdo de help.js, tópico por tópico. Carregado
// por help.html só quando a interface está em inglês (i18n.py). Ao mudar um
// tópico em help.js, mude aqui também.
window.HELP_SECTIONS_I18N = {
    funcionalidades: `
        <h2>Main features</h2>
        <p>One computer runs U-Control, and the other devices on the same network (phone, tablet, another PC) open the Control panel or the screens in a browser. No internet is needed during the service.</p>
        <ul>
            <li><strong>Control:</strong> lyrics with chords, Bible verses, photos, videos and PowerPoint go to the big screen with one tap.</li>
            <li><strong>Synced screens:</strong> the public big screen and the stage monitor follow the Control panel.</li>
            <li><strong>Preparation:</strong> build the order of service, add songs and organize the team schedule ahead of time.</li>
            <li><strong>Bible in two versions</strong> on the big screen at the same time.</li>
            <li><strong>PC screen</strong> and <strong>website on the big screen</strong>, driven from the Control panel.</li>
            <li><strong>Shortcuts</strong> for Stream Deck and other buttons.</li>
            <li><strong>Import songs</strong> from other programs, <strong>backup</strong>, and move songs and services to another computer.</li>
        </ul>
        <p>The big screen can be on the U-Control computer itself (HDMI cable, the most stable option) or on another device on the network.</p>
        <p>The language of the screens (Portuguese or English) is in <a href="/idioma">System → Language · Idioma</a>.</p>`,

    importar: `
        <h2>Import songs from another program</h2>
        <p>In <a href="/importar-musicas">Create → Import songs</a>, choose one or more files. U-Control shows what it found before saving anything.</p>
        <ul>
            <li><strong>Holyrics:</strong> songs exported as JSON.</li>
            <li><strong>OpenLP, OpenSong and others:</strong> OpenLyrics files (<code>.xml</code>), including chords.</li>
            <li><strong>ChordPro</strong> (<code>.cho</code>, <code>.chordpro</code>, <code>.pro</code>…): the chords in brackets become the chord line above the lyrics.</li>
            <li><strong>Text</strong> (<code>.txt</code>), one file per song, and <strong>.zip</strong> files with several of those inside.</li>
        </ul>
        <p>Only new songs come checked. Songs that already exist here (same title and author) are only replaced if you check <strong>replace this computer's version</strong>.</p>
        <div class="callout">Holyrics' own format (<code>.muf</code>) can't be read yet. In Holyrics, export the songs as JSON.</div>`,

    biblia: `
        <h2>Bible in two versions</h2>
        <p>On the Bible pages, next to the translation, choose a <strong>2nd translation</strong>. The big screen then shows the verse in both, one below the other, each with its abbreviation. To go back to one, choose <strong>+ 2nd translation: none</strong>.</p>
        <p>The choice applies to every Control panel and stays after the program restarts.</p>
        <div class="callout">Searching by reference uses the Portuguese book names for now (for example <code>João 3:16</code>, <code>Salmos 23</code>). You can always pick the book and chapter from the list.</div>`,

    powerpoint: `
        <h2>PowerPoint and presentations</h2>
        <ul>
            <li>In the Control panel, under <strong>Photos</strong>, upload the <code>.pptx</code> file (or a PDF). It becomes one image per slide, and all the slides show up in about a minute.</li>
            <li>If the presentation has <strong>animations or transitions</strong>, U-Control also prepares an animated version, tagged <strong>Animated</strong>. The plain slides can be used while it gets ready.</li>
            <li>In the animated version, use <strong>Next</strong> and <strong>Back</strong> (or the arrow keys, the space bar and a pedal) to step through each animation. All screens follow together.</li>
            <li>Fonts embedded in the file (like Canva's) are used, and GIFs move in the animated version.</li>
            <li>Videos inside the slides are split out and show up in the gallery, ready to play on the big screen.</li>
        </ul>
        <div class="callout">On Windows, the conversion needs LibreOffice: check its option in the installer or, if it's missing, use <strong>Install LibreOffice</strong> in <a href="/atualizacao">System → Updates</a>.</div>`,

    site: `
        <h2>PC screen and website on the big screen</h2>
        <h3>PC screen</h3>
        <p>On the computer that will share, open the Control panel and use the <strong>PC screen</strong> tool: the browser asks what to show on the big screen (a window, a tab or the whole screen). Quality depends on the network: on a cable or good Wi-Fi, text stays sharp.</p>
        <h3>Website on the big screen (Windows)</h3>
        <p>The <strong>Website</strong> tool opens a website full screen on the big-screen monitor, in a real browser (Chrome or Edge), and the Control panel drives it: scroll, page down and up, arrows, Enter, zoom, back and reload. It also works from a phone.</p>
        <ul>
            <li>Save the websites you always use to open them with one tap.</li>
            <li>The website browser has its own profile: a login made there once stays saved.</li>
            <li>Only available in the Windows installation, because it has to open a window on the big-screen monitor.</li>
        </ul>`,

    atalhos: `
        <h2>Shortcuts (Stream Deck)</h2>
        <p>In <a href="/atalhos">System → Shortcuts (Stream Deck)</a> you'll find the web addresses that control the big screen: next and previous, go live, black screen, announcement, countdown, clock and the website on the big screen. Any button that calls a web address works: Stream Deck through Companion, QuickDeck and others.</p>
        <ul>
            <li>Each address carries an <strong>access key</strong>. If it leaks, change it on the same page: the old addresses stop working.</li>
            <li><strong>Next</strong> and <strong>previous</strong> follow whatever is live: the website on the big screen, the animated presentation, or what's open in the most recently used Control panel.</li>
        </ul>`,

    backup: `
        <h2>Backup and moving to another computer</h2>
        <h3>Backup (everything)</h3>
        <p>In <a href="/backup">System → Backup</a>, download one file with everything: songs, services, settings, users, photos and audio. To restore, upload that file on the same page, including on another computer running U-Control. Before restoring, the program keeps a copy of what was there.</p>
        <h3>Export and import (only what you choose)</h3>
        <p>In <a href="/pacote">System → Export and import</a>, choose songs, services and photos and take them to another U-Control. For example: prepare at home and use it on the church PC. When importing, you see what's coming and what already exists here before confirming.</p>`,

    primeiro: `
        <h2>First login and users</h2>
        <p>A new installation has no users yet: the login screen asks you to <strong>create the first one</strong> (name, password and the password again). That request disappears as soon as the first user is created.</p>
        <div class="callout">Create this user right after installing: until it exists, whoever opens the login screen first on the network gets to create it.</div>
        <p>After that, each operator gets their own user in <a href="/usuarios">Users</a> (System menu), where you can also change passwords and remove people who no longer use it.</p>
        <p>Use passwords that aren't easy to guess, especially if U-Control can also be reached from the internet.</p>`,

    windows: `
        <h2>The Windows program</h2>
        <ul>
            <li>After installing, open it from the <strong>U-Control</strong> icon on the desktop. The Control panel opens in the browser and the program stays in the <strong>Windows system tray</strong>, next to the clock.</li>
            <li>From the tray menu you open the <strong>Big screen</strong> (the public screen) and the <strong>Stage monitor</strong>. With a second monitor or projector connected, they open there, full screen.</li>
            <li>The menu also shows U-Control's network address, to open it on a phone.</li>
            <li>While U-Control is open, Windows doesn't sleep or turn off the screen (the <strong>Keep the PC awake while the big screen is open</strong> option in the tray menu).</li>
            <li>To turn PowerPoint into slides, check the LibreOffice option in the installer. If it's missing, <strong>System → Updates</strong> shows an <strong>Install LibreOffice</strong> button.</li>
            <li>To shut down, use <strong>Shut down U-Control</strong> in the tray menu or <strong>System → Shut down U-Control</strong>. Closing the windows doesn't stop the program.</li>
            <li>When a new version comes out, U-Control lets you know. Install it from <strong>System → Updates</strong>.</li>
            <li>Songs, photos and settings are kept separately (the <strong>Open data folder</strong> option). Installing a new version over the old one doesn't erase anything.</li>
            <li>The tray menu follows the chosen language after U-Control restarts.</li>
        </ul>`,

    celular: `
        <h2>Using it from a phone or another computer</h2>
        <ul>
            <li>The device has to be on the <strong>same network</strong> (Wi-Fi or cable) as the U-Control computer.</li>
            <li><a href="/links">Links / QR</a> lists the address of each screen, with a QR code to scan with the phone's camera.</li>
            <li>The address looks like <code>http://&lt;computer-ip&gt;:8585</code>.</li>
        </ul>`,

    telas: `
        <h2>Screens that open without logging in</h2>
        <p>The control features require a login, so nobody changes the big screen by accident. These screens open without one, for the display devices and for people who just follow along:</p>
        <ul>
            <li><strong>Public big screen</strong> (<code>/img</code>) and <strong>lyrics for the congregation</strong> (<code>/lyrics/display/public</code>)</li>
            <li><strong>Stage monitor</strong> (<code>/monitor</code>), for the people on stage</li>
            <li><strong>Bible</strong> (<code>/bible/display</code>), <strong>clock</strong> and <strong>countdown</strong></li>
            <li><strong>OBS overlay</strong> (<code>/lyrics/display/obs</code>), with a transparent background for streaming</li>
            <li><strong>Order of service</strong> (<code>/view</code>)</li>
        </ul>`,

    problemas: `
        <h2>Troubleshooting</h2>
        <h3>The phone can't open U-Control</h3>
        <ul>
            <li>Check that the phone is on the same network as the computer, not on mobile data.</li>
            <li>On Windows, the installer allows U-Control through the firewall. If another antivirus or firewall is active, allow port <code>8585</code> in it.</li>
            <li>Some guest networks keep devices apart from each other. In that case, use the church's main network.</li>
        </ul>
        <h3>The video plays without sound on the big screen</h3>
        <p>Browsers block sound that starts on its own. Screens opened from the tray menu (Windows), from <strong>Open on the projector</strong> in the Control panel, or from the script downloaded on the <a href="/dashboard">Home</a> page already have sound allowed. In a regular tab, tap the big screen once.</p>
        <h3>The announcement doesn't show on a screen</h3>
        <p>In the Control panel's <strong>Announcements</strong> panel, check which screens are selected (Public screen, Stage, Stream). Each screen has its own announcement: sending to one doesn't change the others. Below the buttons you can see what's on each screen right now.</p>
        <h3>The screen won't go full screen</h3>
        <p>In the Control panel, use <strong>Open on the projector</strong> to choose which of the computer's screens the public screen opens on.</p>
        <h3>A Bible translation is missing</h3>
        <p>U-Control only ships openly licensed translations (such as the King James Version and the Bible in Basic English in English, and the Bíblia Livre in Portuguese). Copyrighted translations, such as the NIV or ESV, have to be added by whoever has the right to use them.</p>`,

    contato: `
        <h2>Contact</h2>
        <p>U-Control is an open-source project. To report a problem or suggest an improvement, open an issue at <a href="https://github.com/brunomint/U-Control/issues" target="_blank" rel="noopener">github.com/brunomint/U-Control/issues</a>. English is welcome.</p>`,
};

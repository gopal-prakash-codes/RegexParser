var unpackBtn = document.getElementById("unpackBtn");
var parseBtn = document.getElementById("parseBtn");
var thirdBtn = document.getElementById("thirdBtn");
var unpackAgentsDiv = document.getElementById("unpackAgents");
var parseAgentsDiv = document.getElementById("parseAgents");
var thirdAgentsDiv = document.getElementById("parserDiv");


const alertBox = document.getElementById('alert-box');
const alert_message = document.getElementById("alert-message");

if(alertBox){
    const closeBtn = alertBox.querySelector('.alert-modal .close');
    const okBtn = alertBox.querySelector('.alert-modal .ok-btn');
//Listeners

closeBtn.addEventListener('click', function() {
  alertBox.classList.remove('show');
  alert_message.innerText = "";
});

// Hide the modal when the OK button is clicked
okBtn.addEventListener('click', function() {
  alertBox.classList.remove('show');
  alert_message.innerText="";
});
}


/** Displays browser not supported info box for the user*/
function displayBrowserNotSupportedOverlay() {
    overlay.classList.remove("hide");
}

/** Displays browser not supported info box for the user*/
function hideBrowserNotSupportedOverlay() {
    overlay.classList.add("hide");
}


window.addEventListener('DOMContentLoaded', event => {
    // Activate feather
    feather.replace();
    // Enable tooltips globally
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    // Enable popovers globally
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    // Activate Bootstrap scrollspy for the sticky nav component
    const stickyNav = document.body.querySelector('#stickyNav');
    if (stickyNav) {
        new bootstrap.ScrollSpy(document.body, {
            target: '#stickyNav',
            offset: 82,
        });
    }
    // Toggle the side navigation
    const sidebarToggle = document.body.querySelector('#sidebarToggle');
    if (sidebarToggle) {
        // Uncomment Below to persist sidebar toggle between refreshes
        // if (localStorage.getItem('sb|sidebar-toggle') === 'true') {
        //     document.body.classList.toggle('sidenav-toggled');
        // }
        sidebarToggle.addEventListener('click', event => {
            event.preventDefault();
            document.body.classList.toggle('sidenav-toggled');
            localStorage.setItem('sb|sidebar-toggle', document.body.classList.contains('sidenav-toggled'));
        });
    }
    // Close side navigation when width < LG
    const sidenavContent = document.body.querySelector('#layoutSidenav_content');
    if (sidenavContent) {
        sidenavContent.addEventListener('click', event => {
            const BOOTSTRAP_LG_WIDTH = 992;
            if (window.innerWidth >= 992) {
                return;
            }
            if (document.body.classList.contains("sidenav-toggled")) {
                document.body.classList.toggle("sidenav-toggled");
            }
        });
    }
    // Add active state to sidbar nav links
    let activatedPath = window.location.pathname.match(/([\w-]+\.html)/, '$1');
    if (activatedPath) {
        activatedPath = activatedPath[0];
    } else {
        activatedPath = 'index.html';
    }
    const targetAnchors = document.body.querySelectorAll('[href="' + activatedPath + '"].nav-link');
    targetAnchors.forEach(targetAnchor => {
        let parentNode = targetAnchor.parentNode;
        while (parentNode !== null && parentNode !== document.documentElement) {
            if (parentNode.classList.contains('collapse')) {
                parentNode.classList.add('show');
                const parentNavLink = document.body.querySelector(
                    '[data-bs-target="#' + parentNode.id + '"]'
                );
                parentNavLink.classList.remove('collapsed');
                parentNavLink.classList.add('active');
            }
            parentNode = parentNode.parentNode;
        }
        targetAnchor.classList.add('active');
    });

});


// FUnction to apply and saving RegeX

function applyRegex() {
        
    var inputData = document.getElementById("inputData").value;
    var regexPattern = document.getElementById("regexInput").value;
    var errorMessageElement = document.getElementById("error-message");
    errorMessageElement.innerText = "";

    if (regexPattern == ''){
        errorMessageElement.innerText = "* Enter a reguler expression!";;
        return;
    }

    var urlParams = new URLSearchParams(window.location.search);
    var searchedUrlPattern = urlParams.get('searched');

    fetch('/save-regex', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            searched_url_pattern: searchedUrlPattern,
            applied_regex: regexPattern
        })
    })
    .then(response => {
        if (!response.ok) {
            window.location.reload();
            return;
        }
        return response.json();
    })
    .then(data => {
        if (typeof data !== 'undefined') {
            try {
                var regex = new RegExp(regexPattern, "g");
                var matches = inputData.match(regex);
            
                if (matches) {
                    document.getElementById("output").value = matches.join("\n");
                } else {
                    document.getElementById("output").value = "No matches found.";
                }
            } catch (error) {
                document.getElementById("output").value = "Invalid regex pattern: " + error.message;
            }
        }
    })
    .catch(error => {
        console.error('There was a problem with the fetch operation:', error);
    });

}

//hide the RegeX feild error
function removeError() {
    var errorMessageElement = document.getElementById("error-message");
    errorMessageElement.innerText = "";
}



function handleButtonClick(showDiv) {
    var divs = [unpackAgentsDiv, parseAgentsDiv, thirdAgentsDiv];
    divs.forEach(function(div) {
        if (div) {
            div.style.display = (div === showDiv) ? "block" : "none";
        }
    });
}

var buttons = [unpackBtn, parseBtn, thirdBtn];
var divs = [unpackAgentsDiv, parseAgentsDiv, thirdAgentsDiv];

buttons.forEach(function(button, index) {
    button?.addEventListener("click", function() {
        handleButtonClick(divs[index]);
    });
});



document.getElementById('parserSelect')?.addEventListener('change', function() {
    var selectedValue = this.value;
    var regexForm = document.getElementById('regexForm');
    var jsonForm = document.getElementById('jsonForm');

    if (selectedValue === '1') {
        regexForm.style.display = 'block';
        jsonForm.style.display = 'none';
        document.getElementById("jsonOutput").innerText = '';
    } else if(selectedValue === 'select'){
        regexForm.style.display = 'none';
        jsonForm.style.display = 'none';
        document.getElementById("jsonOutput").innerText = '';
        document.getElementById("regexInput").value = '';
        document.getElementById("output").value = '';
    }
    else {
        regexForm.style.display = 'none';
        jsonForm.style.display = 'block';
        document.getElementById("regexInput").value = '';
        document.getElementById("output").value = '';
    }
});

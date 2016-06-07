function groupBy( clusters , sortingFunction ) {

  var groupedClusters = Object.keys(clusters).map(function(cluster) {
    var children = (clusters[cluster].articles.length > 1) ? clusters[cluster].articles : [];
    return {
      'title': '',
      'children': children,
      'info': clusters[cluster],
      'cluster': cluster,
      'holder': true,
      'borderColor': "#A9C7FF"
    };
  }).sort(function(a, b) { return a.cluster - b.cluster });

  return groupedClusters
}

$('#query').submit(function(e) {
  e.preventDefault();

  var group = $(this).find('[name="group"]').val();
  var query = $(this).find('[name="query"]').val();

  $('#canvas, #hiddenCanvas').remove();

  $('.spinner-holder').show();

  $.post('/text-mining/query', JSON.stringify({'group': group, 'query': query}), function (data) {
    data = JSON.parse(data);

    if (data.error === 'bad query') {
      alert('It appears we couldn\'t generate useful clusters with your query, please try another.');
      $('.spinner-holder').hide();
      return;
    }
    
    var dataset = {
      'title': '',
      'children': groupBy(data, function(obj) {return obj['cluster']}),
      'top': true
    };

    $('.spinner-holder').hide();

    drawAll(function(err){ console.log(err) }, dataset);
  });

  return false;
});

  
function drawAll(error, dataset) {
  ////////////////////////////////////////////////////////////// 
  ////////////////// Create Set-up variables  ////////////////// 
  ////////////////////////////////////////////////////////////// 

  var width = Math.max($("#chart").width(),350) - 10,
    height = (window.innerWidth < 768 ? width : window.innerHeight - 10);

  var mobileSize = (window.innerWidth < 768 ? true : false);

  var centerX = width/2,
    centerY = height/2;

  ////////////////////////////////////////////////////////////// 
  /////////////////////// Create SVG  /////////////////////// 
  ////////////////////////////////////////////////////////////// 
  
  //Create the visible canvas and context
  var canvas  = d3.select("#chart").append("canvas")
    .attr("id", "canvas")
    .attr("width", width)
    .attr("height", height);
  var context = canvas.node().getContext("2d");
    context.clearRect(0, 0, width, height);
  
  //Create a hidden canvas in which each circle will have a different color
  //We can use this to capture the clicked on circle
  var hiddenCanvas  = d3.select("#chart").append("canvas")
    .attr("id", "hiddenCanvas")
    .attr("width", width)
    .attr("height", height)
    .style("display","none"); 
  var hiddenContext = hiddenCanvas.node().getContext("2d");
    hiddenContext.clearRect(0, 0, width, height);

  //Create a custom element, that will not be attached to the DOM, to which we can bind the data
  var detachedContainer = document.createElement("custom");
  var dataContainer = d3.select(detachedContainer);

  ////////////////////////////////////////////////////////////// 
  /////////////////////// Create Scales  /////////////////////// 
  ////////////////////////////////////////////////////////////// 

  var colorCircle = d3.scale.ordinal()
      .domain([0,1,2,3])
      .range(['#333','#4c73dd','#4c4c4c','#1c1c1c']);

  var diameter = Math.min(width*0.9, height*0.9),
    radius = diameter / 2;
    
  var zoomInfo = {
    centerX: width / 2,
    centerY: height / 2,
    scale: 1
  };

  //Dataset to swtich between color of a circle (in the hidden canvas) and the node data  
  var colToCircle = {};
  
  var pack = d3.layout.pack()
    .padding(1)
    .size([diameter, diameter])
    .value(function(d) { return d.distance * 100; })
    .sort(function(d) { return d.ID; });

  var bubbleColor = d3.scale.linear()
    .range(['#253C78', '#C576FF']);
    // .range(['#FF7A91', '#B3FFB4']);

  ////////////////////////////////////////////////////////////// 
  ////////////////// Create Circle Packing /////////////////////
  ////////////////////////////////////////////////////////////// 

  var nodes = pack.nodes(dataset),
    oldNode = {},
    currentNode = {},
    holders = [],
    activeCluster = -1,
    root = dataset,
    focus = root;
  
  for (var i=0; i<nodes.length; i++) {
    var node = nodes[i]
    if (node.holder) {
      holders.push(node);
    }
    node.border = false;
    node.borderColor = (node.top == true)? 'rgba(255,255,255,0)' : 'rgba(255,255,255,0.75)';
    if (node.selected || node.holder) {
      node.border = true;
      node.borderColor = (node.selected) ? '#4C73DD' : 'rgba(255,255,255,0.75)';
    }
  }
  ////////////////////////////////////////////////////////////// 
  ///////////////// Canvas draw function ///////////////////////
  ////////////////////////////////////////////////////////////// 
  
  var cWidth = canvas.attr("width");
  var cHeight = canvas.attr("height");
  var colors = d3.scale.linear()
    .range(["#4C377C", "#B45CCF"]);
    // .range(["#967BDD", "#0BE161", "#5A89ED", "#239773", "#E45661", "#E44974", "#A478DE", "#6183E4", "#CC4EED", "#703987"]);
  var nodeCount = nodes.length;
  var drawText = true;
  var mouseX = 0,
    mouseY = 0;

  function updateSize() {
    width = Math.max($("#chart").width(),350) - 10,
    height = (window.innerWidth < 768 ? width : window.innerHeight - 10);
    centerX = width/2;
    centerY = height/2;
    zoomInfo = {
      centerX: width / 2,
      centerY: height / 2,
      scale: 1
    };
  }

  function keywordsOverlayRect(context, node) {
    context.save();

    context.beginPath();
    context.arc(
      ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX,
      ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY,
      node.r * zoomInfo.scale, 0,  2 * Math.PI, true
    );
    context.clip();

    context.fillStyle = "rgba(255,255,255,0.75)";
    context.fillRect(
      ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX - (node.r*zoomInfo.scale),
      ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY - 25,
      (node.r*2)*zoomInfo.scale,
      50
    );

    context.restore();
  }

  function wrapText(context, node) {
    var lineHeight = 16;
    if (node.children && !(node.children.length > 1)) return;

    context.font = '14px proxima-nova-400';
    var maxWidth = (Math.sin(Math.PI/4) * node.r * zoomInfo.scale)*2 - 6;
    var y = ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY;

    if (node.holder) {
      context.textAlign = "center";
      keywordsOverlayRect(context, node);
      context.fillStyle = '#333';
      var words = node.info.keywords.join(', ').split(' ');
      var x = ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX;
      var maxHeight = 50;
    } else {
      context.textAlign = "left";
      context.fillStyle = '#fff';
      var words = node.title.split(' ');
      var x = ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX - (maxWidth/2) + 3;
      var maxHeight = maxWidth;
    }
    
    var currentLine = '';
    var lines = []

    for(var n = 0; n < words.length; n++) {

      var testLine = currentLine + words[n] + ' ';
      var metrics = context.measureText(testLine);
      var testWidth = metrics.width;

      if (testWidth > maxWidth && n > 0) {
        lines.push(currentLine);
        currentLine = words[n] + ' ';
      } else {
        currentLine = testLine
      }
    }
    lines.push(currentLine)
    lines = lines.slice(0, Math.floor(maxHeight/lineHeight));
    
    for (var i=0; i<lines.length; i++) {
      context.fillText(lines[i], x, y - (lines.length*lineHeight)/2 + (i*lineHeight) + 8);
    }
  }

  // The draw function of the canvas that gets called on each frame
  function drawCanvas(chosenContext, hidden) {

    //Clear canvas
    chosenContext.fillStyle = "#333";
    chosenContext.rect(0,0,cWidth,cHeight);
    chosenContext.fill();
    
    //Select our dummy nodes and draw the data to canvas.
    var node = null;
    // It's slightly faster than nodes.forEach()
    for (var i = 0; i < nodeCount; i++) {
      node = nodes[i];

      //If the hidden canvas was send into this function and it does not yet have a color, generate a unique one
      if (hidden) {
        if(node.color == null) {
          // If we have never drawn the node to the hidden canvas get a new color for it and put it in the dictionary.
          node.color = genColor();
          colToCircle[node.color] = node;
        }// if
        // On the hidden canvas each rectangle gets a unique color.
        chosenContext.fillStyle = node.color;
      } else {
        chosenContext.fillStyle = (node.holder || node.top) ? '#333' : colors(node.indico.sentiment);
      }// else

      chosenContext.lineWidth = 2;
      if (node.border != true || node.top == true) {
        chosenContext.strokeStyle = "rgba(255,255,255,0)";
      } else if (node.holder && node.border != true) {
        chosenContext.strokeStyle = "rgba(255,255,255,0.75)";
      } else {
        chosenContext.strokeStyle = node.borderColor;
      }
    
      // Draw each circle
      chosenContext.beginPath();
      chosenContext.arc(
        ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX,
        ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY,
        node.r * zoomInfo.scale, 0,  2 * Math.PI, true
      );
      chosenContext.fill();
      chosenContext.stroke();

      if (node.cluster == focus.cluster && !node.holder) {
        wrapText(context, node);
      }

      //There are several options for setting text
      // chosenContext.font = "20px Open Sans";
      //textAlign supports: start, end, left, right, center
      chosenContext.textAlign = "center";
      //textBaseline supports: top, hanging, middle, alphabetic, ideographic bottom
      chosenContext.textBaseline = "middle";
      chosenContext.fillStyle = "#4169E1";    
    }//for i

    for (var i=0; i<holders.length; i++) {
      var holder = holders[i];

      if (holder.cluster != activeCluster || activeCluster == -1) {
        wrapText(context, holder);
      }
    } // for i in holders

  }//function drawCanvas

  ////////////////////////////////////////////////////////////// 
  /////////////////// Click functionality ////////////////////// 
  ////////////////////////////////////////////////////////////// 

  function findCluster(node) {
    return holders.find(function(holder) {
      return holder.cluster == node.cluster;
    });
  }

  function getClusterKeywords(data) {
    var info = {}
    $.each(data.children, function(i, node) {
      for (var item in node.indico['keywords']) {
        // save every occurence
        if (!info[item]) {
          info[item] = [node.indico['keywords'][item]]
        } else {
          info[item].push(node.indico['keywords'][item])
        }
      }
    });
    return info;
  }

  function getClusterEntities(data, entityType) {
    var info = {}

    $.each(data.children, function(i, node) {
      var entities = node.indico[entityType];
      for (var j=0; j<entities.length; j++) {
        // save every occurence
        if (entities[j].text.length > 30) {
          continue;
        } else if (!info[entities[j].text]) {
          info[entities[j].text] = [{ position: entities[j].position, article: i, cluster: data.cluster, type: entityType }]
        } else {
          info[entities[j].text].push({ position: entities[j].position, article: i, cluster: data.cluster, type: entityType });
        }
      }
    });
    return info;
  }

  function getClusterSentiment(data) {
    var info = {'positive': [], 'neutral': [], 'negative': []}

    $.each(data.children, function(i, node) {
      var sentiment = node.indico['sentiment'];
      var articleSentiment = { article: i, cluster: data.cluster, sentiment: sentiment };
      switch (true) {
        case sentiment < 0.25:
          info['negative'].push(articleSentiment);
          break;
        case sentiment < 0.75:
          info['neutral'].push(articleSentiment);
          break;
        case sentiment > 0.75:
          info['positive'].push(articleSentiment);
          break;
      }
    });
    return info;
  }

  function combine(data) {
    var total = {}
    $.each(data, function (i, clusterItems) {
      for (var item in clusterItems) {
        if (!total[item]) {
          total[item] = clusterItems[item];
        } else {
          total[item].concat(clusterItems[item]);
        }
      }
    });
    return total;
  }

  function topItems(data, num) {
    var topKeys = Object.keys(data).sort(function(a, b) {return -(data[a].length - data[b].length) }).slice(0, num);
    var top = {}
    $.each(topKeys, function(i, key) { top[key] = data[key]; });
    return top;
  }

  function writeList(data, selector) {
    $(selector).html('');
    for (var key in data) {
      $(selector).append('<li class="word">\
        <span class="name">'+key+'</span><span class="mentions">'+data[key].length.toString()+'</span>\
      </li>');
    }
  }

  function populateNodeInfo(data) {
    updateText(data, ['keywords', 'people', 'places', 'organizations'], '#info');
    updateBar('#node .sentiment-bar', data.indico.sentiment);

    $('#node .text p').html(data.summary);
    $('#node .length').text(data.text.split(' ').length);
    $('#node .title').find('a').attr('href', data.link);
    $('#node .title').find('a').text(data.title);

    if (data.date) {
      $('#node .date').show();
      $('#node .date').text(new Date(data.date*1000).toDateString());
    } else {
      $('#node .date').hide();
    }
  }

  function populateClusterInfo(data) {
    $('#cluster .articles').text(data.children.length.toString());

    var entityChunks = [
      getClusterEntities(data, 'people'),
      getClusterEntities(data, 'places'),
      getClusterEntities(data, 'organizations')
    ];

    var topEntities = topItems(combine(entityChunks), 5);
    var topKeywords = topItems(getClusterKeywords(data), 5);
    writeList(topKeywords, '#cluster .keywords');
    writeList(topEntities, '#cluster .entities');

    var growthObjects = [];
    var growthStrings = [];
    data.children.map(function(article) {
      for (var i=0; i<article.growth.length; i++) {
        if (growthStrings.indexOf(article.sentences[i]) < 0) {
          growthObjects.push({ sentence: article.sentences[i], growth: article.growth[i], color: article.color })
          growthStrings.push(article.sentences[i]);
        }
      }
    });

    var topGrowth = growthObjects.filter(function(growthSentence) {
      return growthSentence.sentence.length > 30;
    }).sort(function(a, b) {
      return Math.max(b.growth.positive, b.growth.negative) - Math.max(a.growth.positive, a.growth.negative);
    }).slice(0, 10);

    $('#cluster .growth').html('');
    topGrowth.map(function(growthSentence) {
      $('#cluster .growth').append('<li color="'+growthSentence.color+'">'+growthSentence.sentence+'</li>');
    });

    $('#cluster .growth li').click(function() {
      var node = colToCircle[$(this).attr('color')];
      node.selected = true;
      node.border = true;
      slideInfoOut(node, 'node');
      drawCanvas(hiddenContext, true);
    });
  }

  function createDistribution(overallSentiment) {
    var total = {'positive': [], 'neutral': [], 'negative': []}
    $.each(overallSentiment, function(i, clusterSentiment) {
      for (var key in total) {
        total[key] = total[key].concat(clusterSentiment[key]);
      }
    });

    var ctx = document.getElementById('sentiment-graph').getContext('2d');
    var data = {
      labels: [
        "Positive",
        "Neutral",
        "Negative"
      ],
      datasets: [{
        data: [
          total.positive.length,
          total.neutral.length,
          total.negative.length
        ],
        backgroundColor: [
            "#00C75A",
            "#E7F6E4",
            "#ED686D"
        ],
        hoverBackgroundColor: [
            "#00C75A",
            "#E7F6E4",
            "#ED686D"
        ]
      }]
    };
    var myDoughnutChart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
          legend: {
            labels: {
              fontColor: "white",
              strokeStyle: "rgba(0,0,0,0)"
            }
          }
        }
    });
  }

  function populateOverview(data) {

    var totalClusters = data.children.length;
    var totalArticles = 0;
    $.each(data.children, function(i, cluster) {
      totalArticles += cluster.children.length;
    });
    $('#top .article-meta .query-word').html('<b>'+$('input[name="query"]').val()+'</b>');
    $('#top .clusters').html(totalClusters.toString());
    $('#top .articles').html(totalArticles.toString());

    var keywordChunks = [];
    var peopleChunks = [];
    var placesChunks = [];
    var organizationsChunks = [];
    var overallSentiment = [];
    $.each(data.children, function(i, cluster) {
      keywordChunks.push(getClusterKeywords(cluster));
      peopleChunks.push(getClusterEntities(cluster, 'people'));
      placesChunks.push(getClusterEntities(cluster, 'places'));
      organizationsChunks.push(getClusterEntities(cluster, 'organizations'));
      overallSentiment.push(getClusterSentiment(cluster));
    });
    var entityChunks = [].concat(peopleChunks, placesChunks, organizationsChunks);

    var topEntities = topItems(combine(entityChunks), 10);
    var topKeywords = topItems(combine(keywordChunks), 10);
    writeList(topKeywords, '#top .keywords');
    writeList(topEntities, '#top .entities');
    createDistribution(overallSentiment);
  }


  function slideInfoOut(data, dataType) {
    $('#info > div').hide();

    if (dataType === 'node') {
      $('#info #node').show();
      populateNodeInfo(data);
    } else if (dataType === 'cluster') {
      $('#info #cluster').show();
      populateClusterInfo(data);
    } else if (dataType === 'top') {
      $('#info #top').show();
      populateOverview(data);
    } else {
      throw new Error('Invalid data type');
    }

    $('#banner').css({'right': '400px'});
    $('#info').css({'right': '0px'});
    $('#chart').css({'right': '200px'});
  }

  function slideInfoIn() {
    $('#banner').css({'right': '0px'});
    $('#info').css({'right': '-400px'});
    $('#chart').css({'right': '0px'});
    updateSize();
  }
  
  // Listen for clicks on the main canvas
  document.getElementById("canvas").addEventListener("click", function(e){
    //Figure out where the mouse click occurred.
    mouseX = e.layerX;
    mouseY = e.layerY;

    // Get the corresponding pixel color on the hidden canvas and look up the node in our map.
    // This will return that pixel's color
    var col = hiddenContext.getImageData(mouseX, mouseY, 1, 1).data;
    //Our map uses these rgb strings as keys to nodes.
    var colString = "rgb(" + col[0] + "," + col[1] + ","+ col[2] + ")";
    currentNode = colToCircle[colString];

    // We actually only need to draw the hidden canvas when there is an interaction. 
    // This sketch can draw it on each loop, but that is only for demonstration.
    drawCanvas(hiddenContext, true);
    for (var i=0; i<nodeCount; i++) {
      var node = nodes[i];
      
      if (node.selected) {
        node.border = false;
        node.borderColor = '#4C73DD';
        node.selected = false;
      }
    }

    if (currentNode) {
      var cluster = findCluster(currentNode);
      if (cluster && !currentNode.top) {
        zoomToCanvas(cluster);
        if (!currentNode.holder) slideInfoOut(currentNode, 'node');
      } else {
        zoomToCanvas(root);
      }
      currentNode.selected = (!currentNode.holder)? true : false;
    } else {
      setBanner({});
      zoomToCanvas(root);
    }
  
  });

  ////////////////////////////////////////////////////////////// 
  /////////////////// Hover functionality ////////////////////// 
  //////////////////////////////////////////////////////////////
  function uniqueBy(a, key) {
      var seen = {};
      return a.filter(function(item) {
          var k = key(item);
          return seen.hasOwnProperty(k) ? false : (seen[k] = true);
      });
  }

  function showTop (article, indicoSelector) {
    var uniques = uniqueBy(article.indico[indicoSelector], function(obj) { return obj.text }).filter(function(entity) {
      return entity.text.length < 15;
    });
    return uniques.slice(0, 3).map(function(entityMetadata) {
      return entityMetadata.text;
    }).join(', ');
  }

  function updateText(node, listOfSelectors, parent) {
    var parent = parent || '';
    for (var i=0; i<listOfSelectors.length; i++) {
      var selector = listOfSelectors[i];

      if (node.indico[selector].length > 0) {
        var info = showTop(node, selector);
        if (!info) continue;

        $(parent+' .'+selector).html('<p>\
          <b>'+selector[0].toUpperCase()+selector.slice(1)+'</b> '+info+'<br><br>\
        </p>')
      } else {
        $(parent+' .'+selector).html('')
      }
    }
  }

  function updateBar(barSelector, percent) {
    var $barHolder = $(barSelector)
    var $label = $barHolder.find('.label');

    $label.hide();
    var textPercent = parseInt(percent*100).toString()+'%';
    $barHolder.find('.data').width(parseInt(percent*100).toString()+'%');
    $label.html(textPercent+' positive');
    
    if (percent > 0.5) {
      var labelPosRight = '15px', color = '#FFF', font = '"proxima-nova-400"';
    } else {
      var labelPosRight = '-100px', color = '#4C73DD', font = '"proxima-nova-600"';
    }

    $label.css({ 'right': labelPosRight, 'color': color, 'font-family': font });
    $label.fadeIn('fast');
  }

  function setTooltip (node, mouseX, mouseY) {
    if (node.holder == true || node.top == true || Object.is(node, {})) {
      $('#tooltip').stop(true, true);
      $('#tooltip').hide();
      return;
    }

    // updateText(node, ['keywords', 'people', 'places', 'organizations'], '#tooltip');
    var top = (centerY > mouseY) ? mouseY-80 : mouseY-$('#tooltip').height();
    var left = (centerX > mouseX) ? mouseX+75 : mouseX-375;
    // var nodeX = ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX;
    // var nodeY = ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY;
    // var top = (centerY > nodeX) ? nodeY-20 : nodeY-$('#tooltip').height();
    // var left = nodeX+50;

    $('#tooltip').css("top", top.toString()+"px");
    $('#tooltip').css("left", left.toString()+"px");
    $('#tooltip .title').text(node.title);
    
    $('#tooltip').stop(true, true);
    $('#tooltip').show();
  }

  function setBanner(node) {
    if (!Object.keys(node).length) {
      console.log('cooock');
      $('#banner').hide();
      return
    } else {
      $('#banner').show();
    }

    // var clusterIndico = findCluster(node);
    // var info = clusterIndico.info.keywords.join(', ');
    // $('#banner > span').text(info);
  }

  document.getElementById('tooltip').addEventListener('mouseover', function(e) {
    $('#tooltip').stop(true, true);
    $('#tooltip').hide();
  });

  document.getElementById("canvas").addEventListener("mousemove", function(e) {
    //Figure out where the mouse click occurred.
    mouseX = e.layerX;
    mouseY = e.layerY;

    // Get the corresponding pixel color on the hidden canvas and look up the node in our map.
    // This will return that pixel's color
    var col = hiddenContext.getImageData(mouseX, mouseY, 1, 1).data;
    //Our map uses these rgb strings as keys to nodes.
    var colString = "rgb(" + col[0] + "," + col[1] + ","+ col[2] + ")";
    currentNode = colToCircle[colString];

    if (!Object.is(oldNode, currentNode)) {
      oldNode = currentNode;

      // We actually only need to draw the hidden canvas when there is an interaction. 
      // This sketch can draw it on each loop, but that is only for demonstration. 
      for (var i=0; i<nodeCount; i++) {
        var node = nodes[i]
        node.border = false;
        node.borderColor = (node.top == true)? 'rgba(255,255,255,0)' : 'rgba(255,255,255,0.75)';
        if (node.selected || node.holder) {
          node.border = true;
          node.borderColor = (node.selected) ? '#4C73DD' : 'rgba(255,255,255,0.75)';
        }
      }

      drawCanvas(hiddenContext, true);

      if (currentNode) {
        setBanner(currentNode);
        currentNode.border = true;
        activeCluster = (currentNode.top)? -1 : currentNode.cluster;

        if (!Object.is(focus, root)) setTooltip(currentNode, e.clientX, e.clientY);

        if (currentNode.cluster != undefined) {
          var cluster = findCluster(currentNode);
          cluster.border = true;
        }
      } else {
        setTooltip({}, 0, 0);
      }

      if (activeCluster === -1) setBanner({});
    }

  });

  ////////////////////////////////////////////////////////////// 
  ///////////////////// Zoom Function //////////////////////////
  ////////////////////////////////////////////////////////////// 

  $('#add-data').click(function(e) { 
    // TEMPORARY
    e.preventDefault();
    return false;
  });

  $('#zoomOut').click(function(e) {
    e.preventDefault();
    zoomToCanvas(root);
    return false;
  });
  
  //Based on the generous help by Stephan Smola
  //http://bl.ocks.org/smoli/d7e4f9199c15d71258b5
  
  var ease = d3.ease("cubic-in-out"),
    duration = 2000,
    timeElapsed = 0,
    interpolator = null,
    vOld = [focus.x, focus.y, focus.r * 2.05];
    
  //Create the interpolation function between current view and the clicked on node
  function zoomToCanvas(focusNode) {
    focus = focusNode;

    if (focusNode == root) {
      slideInfoOut(dataset, 'top');
      $('#zoomOut').animate({ 'opacity': 0});
    } else if (focusNode.holder) {
      slideInfoOut(focusNode, 'cluster');
      $('#zoomOut').animate({ 'opacity': 1});
    } else {
      slideInfoOut(focusNode, 'node');
      $('#zoomOut').animate({ 'opacity': 1});
    }
    
    $('#tooltip').hide();
    drawText = false;

    var v = [focusNode.x, focusNode.y, focusNode.r * 2.05]; //The center and width of the new "viewport"
    
    interpolator = d3.interpolateZoom(vOld, v); //Create interpolation between current and new "viewport"
    
    duration =  interpolator.duration; //Interpolation gives back a suggested duration      
    timeElapsed = 0; //Set the time elapsed for the interpolateZoom function to 0 
    vOld = v; //Save the "viewport" of the next state as the next "old" state
  }//function zoomToCanvas
  
  //Perform the interpolation and continuously change the zoomInfo while the "transition" occurs
  function interpolateZoom(dt) {
    if (interpolator) {
      timeElapsed += dt;
      var t = ease(timeElapsed / duration);
      
      zoomInfo.centerX = interpolator(t)[0];
      zoomInfo.centerY = interpolator(t)[1];
      zoomInfo.scale = diameter / interpolator(t)[2];
    
      if (timeElapsed >= duration) {
        interpolator = null;
        drawText = true;
      }
    }//if
  }//function interpolateZoom
  
  ////////////////////////////////////////////////////////////// 
  //////////////////// Other Functions /////////////////////////
  ////////////////////////////////////////////////////////////// 
  
  //Generates the next color in the sequence, going from 0,0,0 to 255,255,255.
  //From: https://bocoup.com/weblog/2d-picking-in-canvas
  var nextCol = 1;
  function genColor(){
    var ret = [];
    // via http://stackoverflow.com/a/15804183
    if(nextCol < 16777215){
      ret.push(nextCol & 0xff); // R
      ret.push((nextCol & 0xff00) >> 8); // G 
      ret.push((nextCol & 0xff0000) >> 16); // B

      nextCol += 100; // This is exagerated for this example and would ordinarily be 1.
    }
    var col = "rgb(" + ret.join(',') + ")";
    return col;
  }//function genColor

  ////////////////////////////////////////////////////////////// 
  /////////////////////// Initiate ///////////////////////////// 
  ////////////////////////////////////////////////////////////// 
      
  //First zoom to get the circles to the right location
  zoomToCanvas(root);
  
  var dt = 0;
  d3.timer(function(elapsed) {
    interpolateZoom(elapsed - dt);
    dt = elapsed;
    drawCanvas(context);
  });

}//drawAll
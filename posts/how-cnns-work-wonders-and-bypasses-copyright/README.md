---
title: "How CNN's Work Wonders and Bypasses Copyright"
slug: how-cnns-work-wonders-and-bypasses-copyright
id: 6708eb9447b6c200019d02be
published_at: 2024-04-25T02:29:00.000-07:00
updated_at: 2025-01-02T17:21:29.000-08:00
featured: False
reading_time: 5 min
feature_image: https://tokenwisdom.ghost.io/content/images/2024/10/img-oqHp1o4Z19dkCOA7bxnTY.jpeg
excerpt: "W15 - CNNs: The AI pasta maker that turns dog photos into digital spaghetti, slicing and dicing pixels until—voila!—it barks 'Woof!' Ethical food for thought: Is your AI's training data al dente or half-baked?\""
url: https://tokenwisdom.ghost.io/how-cnns-work-wonders-and-bypasses-copyright/
tags:
  - name: 👁️ A Closer Look
    slug: a-closer-look
  - name: Deep Tech
    slug: deeptech
  - name: A.I. (and Subsets)
    slug: ai
  - name: Emerging Tech
    slug: emerging-technology
  - name: Ethics \ Principles
    slug: ethical
  - name: Innovation
    slug: innovation
  - name: Technology
    slug: technology
  - name: Generative AI
    slug: generative
  - name: IP \ Copyright
    slug: copyright
authors:
  - name: 🌶️ @iamkhayyam 
    slug: iamkhayyam
---

# How CNN's Work Wonders and Bypasses Copyright

"The journey of life is sweeter when traveled with a dog."


How CNNs Work: The Pasta Maker That Recognizes Dogs

Imagine having a magical pasta maker that can recognize dogs. As whimsical as it sounds, this analogy helps demystify Convolutional Neural Networks (CNNs), a type of artificial intelligence remarkably adept at recognizing patterns in visual data. Let's break this down step by step, with some insights from helpful resources.

Andreas Horn on LinkedIn: #deeplearning #artificialintelligence #ai | 113 comments𝗧𝗵𝗶𝘀 𝗶𝘀 𝗯𝘆 𝗳𝗮𝗿 𝘁𝗵𝗲 𝗯𝗲𝘀𝘁 𝗮𝗻𝗱 𝘀𝗶𝗺𝗽𝗹𝗲𝘀𝘁 𝗲𝘅𝗽𝗹𝗮𝗻𝗮𝘁𝗶𝗼𝗻 𝗼𝗳 𝗖𝗡𝗡𝘀 (𝗖𝗼𝗻𝘃𝗼𝗹𝘂𝘁𝗶𝗼𝗻𝗮𝗹 𝗡𝗲𝘂𝗿𝗮𝗹… | 113 comments on LinkedInLinkedInAndreas Horn


The Input: Your Dog Photo

Imagine feeding a photo of a dog into this fantastic pasta maker, much like you place dough into the machine. The photo, composed of pixels, each with color and intensity information, enters the CNN prepared for intricate processing through multiple stages.


The Pasta Maker: Vertical and Horizontal Cuts

Convolutional layers in CNNs work in stages, much like our pasta maker, which cuts the image into strips:

 1. First Pass: Vertical Strips The original image passes through the pasta maker, which cuts it vertically into 'n' strips. For simplicity, let's say the image is divided into even and odd-numbered strips. These are then combined to create two new images:
    * Even Strips: One image containing all even-numbered vertical strips.
    * Odd Strips: Another image containing all odd-numbered vertical strips.
 2. Second Pass: Horizontal Strips Each of these two images now goes through the pasta maker again, but this time horizontally, creating new strips. We then alternate and combine these strips to create four new images:
    * Top Even strips from Vertical-Even: Contains alternating horizontal strips from the even-strips image.
    * Top Even strips from Vertical-Odd: Contains alternating horizontal strips from the odd-strips image.
    * Bottom Even strips from Vertical-Even: Similarly divided.
    * Bottom Even strips from Vertical-Odd: Similarly divided.

Through these layered steps, the convolutional layers of CNNs increasingly capture both broad and fine details like shapes, textures, and complex features.


The Pooling Layers: Compressing the Pasta

Pooling layers function as a means to compress the information collected so far. Think of it as taking your freshly made pasta and rolling it into a tidy, compacted bundle. Despite the compression, vital qualities remain preserved, making the data easier to process in subsequent layers.


The Fully Connected Layers: The Taste Test

Finally, the fully connected layers act as the connoisseur in our analogy. All collected and refined data is brought together, and these layers analyze the compacted details to make a final decision, akin to a taste test that declares, "Indeed, that's a dog!"





Algorithm: Pasta Dog Detector

To encapsulate this process, let's define an algorithm for our "Pasta Dog Detector," which simplifies the methodology:
























0:00

/0:15


1×
















 1. Initialization
    * Load the image of a dog (or any object) as the input.
    * Pre-process the image by normalizing the pixel values.
 2. First Pass: Vertical Strips
    * Divide the image into 'n' vertical strips.
    * Create two new images:
      * Even Strips Image: Combine all even-numbered vertical strips.
      * Odd Strips Image: Combine all odd-numbered vertical strips.
 3. Second Pass: Horizontal Strips
    * For both the Even Strips Image and the Odd Strips Image:
      * Divide each image into 'm' horizontal strips.
      * Create four new images:
        * Top Even strips from Vertical-Even: Alternating horizontal strips from the even-strips image.
        * Top Even strips from Vertical-Odd: Alternating horizontal strips from the odd-strips image.
        * Bottom Even strips from Vertical-Even: Similarly divided.
        * Bottom Even strips from Vertical-Odd: Similarly divided.
























0:00

/0:28


1×
















 1. Convolutional Layers: Feature Extraction
    * Apply a series of convolutional operations to each of the four images to capture key features:
      * Detect edges and basic shapes.
      * Detect textures and patterns.
      * Detect complex features like eyes and paws.
 2. Pooling Layers: Data Compression
    * Apply pooling operations to reduce the spatial dimensions of the images while preserving important information.
 3. Fully Connected Layers: Decision Making
    * Flatten the pooled feature maps into a 1D vector.
    * Pass the flattened vectors through fully connected layers.
    * Use activation functions to introduce non-linearity.
    * The final layer provides probabilities indicating the likelihood that the input image is of a specific class (e.g., dog).
 4. Model Training
    * Train the detector using labeled image datasets.
    * Use optimization techniques such as gradient descent.
 5. Inference and Classification
    * Feed a new input image through the trained detector.
    * Obtain the final classification result.


Diffusion Models: Legal and Ethical Considerations

While CNNs are traditionally used for image recognition, it's important to mention diffusion models, particularly in the context of AI-generated art. Diffusion models work by iteratively refining a noisy version of an image back into a clear, high-fidelity representation. Unlike CNNs, diffusion models do not store actual image data. Rather, they process the data to such an extent that the original image is essentially diffused beyond recognition, thus theoretically circumventing direct copyright infringement.

However, the ethical sourcing of training material for these models is often contentious. The datasets used to train diffusion models are frequently acquired through nefarious means or under "ask for forgiveness later" scenarios. This practice raises significant ethical questions regarding the rights of original content creators and the overall moral responsibility of utilizing such training data.


The Magic of CNNs and Real-World Implications

Think of the viral video where you can still recognize a dog even when the image is minimized to 25% of its actual size. This vivid example showcases how CNNs recognize what's essential without needing the full image, making the process faster and more efficient.

The prowess of CNNs extends far beyond recognizing our furry friends. In healthcare, they aid in detecting diseases by pinpointing subtle changes in medical imagery, raising diagnostic accuracy. In the realm of self-driving cars, CNNs identify and respond to road signs, pedestrians, and other driving conditions, ensuring safety and efficacy. In essence, these "pasta makers" are revolutionizing how machines perceive and interact with visual information.


A Nod to Everyday Magic

Next time you’re making pasta, remember that while your pasta maker might not distinguish a dog from a cat, the AI behind your everyday technology can. Convolutional Neural Networks, functioning similarly to our whimsical pasta maker, encapsulate the astounding technological advances that simplify complex visual recognition and transform numerous industries.

However, as we expand the capabilities of AI with models like diffusion models, we must do so ethically. Proper sourcing of training material is crucial to ensure that we respect the rights of original creators while continuing to innovate.








Don't forget to check out the weekly roundup: It's Worth A Fortune!